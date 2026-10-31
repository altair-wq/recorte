"""Integrity: deterministic pre-checks + LLM context check (Haiku). Never crashes the pipeline."""
from __future__ import annotations

import json
import logging
import re
import time
import unicodedata

from .. import config, db
from ..models import Flag, Integrity, Transcript
from . import compact
from .moments import load_prompt

log = logging.getLogger(__name__)

TOOL = {
    "name": "report_integrity",
    "description": "Report the integrity assessment of the proposed span.",
    "input_schema": {
        "type": "object",
        "properties": {
            "score": {"type": "integer", "minimum": 0, "maximum": 100},
            "flags": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": ["missing_qualifier", "missing_attribution", "question_without_answer", "hypothetical_or_sarcasm", "needs_prior_context"]},
                        "evidence": {"type": "string"},
                        "at_utt": {"type": "integer"},
                        "suggestion": {"type": "string"},
                    },
                    "required": ["type", "evidence", "at_utt"],
                },
            },
            "suggested_start_utt": {"type": "integer"},
            "suggested_end_utt": {"type": "integer"},
            "rationale": {"type": "string"},
        },
        "required": ["score", "flags", "suggested_start_utt", "suggested_end_utt", "rationale"],
    },
}

PENALTY = {"mid_sentence_cut": 25, "missing_qualifier": 35, "missing_attribution": 35, "question_without_answer": 20,
           "hypothetical_or_sarcasm": 40, "needs_prior_context": 15, "speaker_change_at_edge": 8}


# ---- deterministic -------------------------------------------------------

def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


COND_RE = re.compile(r"(^|[,;]\s*|\by\s+|\bpero\s+)(si|en caso de|siempre que|salvo|solo si|a menos que|siempre y cuando)\b")
DEMONSTRATIVE_RE = re.compile(r"^(eso|esa|ese|esto|esta|este|aquello|lo que dije|como dije|como expliqu)")
ATTR_RE = re.compile(r"\b(segun|dijo que|dicen que|dice que|sostienen|afirman|la oposicion dice|algunos dicen)\b")
SARCASM_RE = re.compile(r"\b(claro, y|eso es lo que dicen|no es serio|ironicamente|supuestamente)\b")


def deterministic_checks(tr: Transcript, start_utt: int, end_utt: int) -> list[Flag]:
    flags: list[Flag] = []
    s = tr.by_id(start_utt)
    e = tr.by_id(end_utt)
    if s is None or e is None:
        return flags
    prev = tr.by_id(start_utt - 1)
    nxt = tr.by_id(end_utt + 1)
    span_text = tr.text_between(start_utt, end_utt)

    # mid_sentence_cut guard: span starts in lowercase (continuation) or ends without terminal punctuation
    first_word = s.text.strip()[:1]
    if first_word and first_word.islower() and prev is not None and not re.search(r"[.!?…]$", prev.text.strip()):
        flags.append(Flag(type="mid_sentence_cut", evidence=prev.text, at=prev.start, suggestion=f"extend start to u{prev.id}"))
    if not re.search(r"[.!?…\"”»]$", e.text.strip()) and nxt is not None:
        flags.append(Flag(type="mid_sentence_cut", evidence=e.text, at=e.end, suggestion=f"extend end to u{nxt.id}"))

    # speaker_change_at_edge: same speaker continues within < 0.6 s across the cut
    if prev is not None and prev.speaker == s.speaker and s.start - prev.end < 0.6:
        flags.append(Flag(type="speaker_change_at_edge", evidence=prev.text, at=prev.start, suggestion=f"extend start to u{prev.id}"))
    if nxt is not None and nxt.speaker == e.speaker and nxt.start - e.end < 0.6:
        flags.append(Flag(type="speaker_change_at_edge", evidence=nxt.text, at=nxt.start, suggestion=f"extend end to u{nxt.id}"))

    # question_without_answer: span opens with a question and ends before another speaker answers
    if s.text.strip().endswith("?"):
        answered = any(u.speaker != s.speaker for u in tr.utterances if start_utt < u.id <= end_utt)
        if not answered and nxt is not None:
            flags.append(Flag(type="question_without_answer", evidence=s.text, at=s.start, suggestion=f"extend end to u{nxt.id}"))

    # lexical hints (cheap stand-in for the LLM when it is unavailable; the LLM check adds to these)
    span_f = _fold(span_text)
    continues_prev = bool(first_word) and (first_word.islower() or DEMONSTRATIVE_RE.match(_fold(s.text)) is not None)
    before = [u for u in tr.utterances if u.id < start_utt and u.end >= s.start - config.CONTEXT_WINDOW_S]
    for u in before[-2:]:
        f = _fold(u.text)
        dangling = u.text.strip().endswith((",", ";", ":")) or first_word.islower()
        if COND_RE.search(f) and not COND_RE.search(span_f) and dangling:
            flags.append(Flag(type="missing_qualifier", evidence=u.text, at=u.start, suggestion=f"extend start to u{u.id}"))
        if ATTR_RE.search(f) and continues_prev:
            flags.append(Flag(type="missing_attribution", evidence=u.text, at=u.start, suggestion=f"extend start to u{u.id}"))
    if continues_prev and prev is not None and not first_word.islower():
        flags.append(Flag(type="needs_prior_context", evidence=prev.text, at=prev.start, suggestion=f"extend start to u{prev.id}"))
    if ATTR_RE.search(_fold(s.text)) and e.id == s.id and nxt is not None:
        flags.append(Flag(type="missing_attribution", evidence=s.text, at=s.start, suggestion=f"extend end to u{nxt.id}"))
    if SARCASM_RE.search(_fold(s.text)) and e.id == s.id and nxt is not None:
        flags.append(Flag(type="hypothetical_or_sarcasm", evidence=nxt.text, at=nxt.start, suggestion=f"extend end to u{nxt.id}"))
    flags.sort(key=lambda f: -PENALTY.get(f.type, 10))
    return _dedupe(flags)


def _dedupe(flags: list[Flag]) -> list[Flag]:
    seen: set[tuple[str, float]] = set()
    out: list[Flag] = []
    for f in flags:
        k = (f.type, round(f.at, 1)) if f.type in ("mid_sentence_cut", "speaker_change_at_edge") else (f.type, 0.0)
        if k not in seen:
            seen.add(k)
            out.append(f)
    return out


def _suggest(tr: Transcript, start_utt: int, end_utt: int, flags: list[Flag]) -> tuple[int, int]:
    s, e = start_utt, end_utt
    for f in flags:
        m = re.search(r"extend (start|end) to u(\d+)", f.suggestion or "")
        if not m:
            continue
        uid = int(m.group(2))
        if m.group(1) == "start":
            s = min(s, uid)
        else:
            e = max(e, uid)
    return s, e




def heuristic_score(flags: list[Flag]) -> int:
    return max(5, 96 - sum(PENALTY.get(f.type, 10) for f in flags))


# ---- LLM ------------------------------------------------------------------

def _llm_check(tr: Transcript, start_utt: int, end_utt: int) -> tuple[Integrity | None, str]:
    if not config.ANTHROPIC_API_KEY:
        return None, "no key"
    import anthropic

    block = compact.context_block(tr, start_utt, end_utt, config.CONTEXT_WINDOW_S)
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    t0 = time.time()
    resp = client.messages.create(
        model=config.INTEGRITY_MODEL, max_tokens=800, temperature=0, system=load_prompt("integrity_check.md"),
        tools=[TOOL], tool_choice={"type": "tool", "name": "report_integrity"},
        messages=[{"role": "user", "content": f"Proposed clip u{start_utt}-u{end_utt}.\n\n{block}"}],
    )
    u = resp.usage
    db.log_call("integrity.llm", (time.time() - t0) * 1000, model=config.INTEGRITY_MODEL,
                est_cost_usd=u.input_tokens / 1e6 * 1 + u.output_tokens / 1e6 * 5, input_tokens=u.input_tokens, output_tokens=u.output_tokens)
    for b in resp.content:
        if b.type == "tool_use" and isinstance(b.input, dict):
            d = b.input
            flags: list[Flag] = []
            for f in d.get("flags", []):
                utt = tr.by_id(int(f.get("at_utt", start_utt)))
                flags.append(Flag(type=f["type"], evidence=str(f.get("evidence", ""))[:300], at=utt.start if utt else 0.0, suggestion=f.get("suggestion")))
            ss = tr.by_id(int(d.get("suggested_start_utt", start_utt)))
            se = tr.by_id(int(d.get("suggested_end_utt", end_utt)))
            return Integrity(score=int(d.get("score", 50)), flags=flags, suggested_start=ss.start if ss else None,
                             suggested_end=se.end if se else None, checked_with=config.INTEGRITY_MODEL, rationale=d.get("rationale")), "ok"
    return None, "no tool call"


def _fixture_cached(start_utt: int, end_utt: int) -> Integrity | None:
    p = config.FIXTURES_DIR / "integrity.json"
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    hit = data.get(f"{start_utt}-{end_utt}")
    return Integrity.model_validate(hit) if hit else None


# ---- entry ----------------------------------------------------------------

def check(tr: Transcript, start_utt: int, end_utt: int, *, use_fixture: bool = False) -> Integrity:
    det = deterministic_checks(tr, start_utt, end_utt)
    llm: Integrity | None = None
    how = "deterministic"
    if use_fixture or not config.ANTHROPIC_API_KEY:
        llm = _fixture_cached(start_utt, end_utt)
        how = "fixture" if llm else "deterministic"
    else:
        try:
            llm, why = _llm_check(tr, start_utt, end_utt)
            how = config.INTEGRITY_MODEL if llm else f"deterministic ({why})"
        except Exception as e:  # noqa: BLE001
            log.warning("integrity LLM failed: %s", e)
            det.append(Flag(type="needs_prior_context", evidence="check unavailable", at=tr.by_id(start_utt).start if tr.by_id(start_utt) else 0.0))
            how = "deterministic (llm error)"

    flags = _dedupe(det + (llm.flags if llm else []))
    s_utt, e_utt = _suggest(tr, start_utt, end_utt, flags)
    ss, se = tr.by_id(s_utt), tr.by_id(e_utt)
    if llm:
        score = min(llm.score, heuristic_score(det)) if det else llm.score
        if llm.suggested_start is not None:
            ss_t = min(llm.suggested_start, ss.start if ss else llm.suggested_start)
        else:
            ss_t = ss.start if ss else None
        se_t = max(llm.suggested_end, se.end) if (llm.suggested_end is not None and se) else (se.end if se else None)
        rationale = llm.rationale
    else:
        score = heuristic_score(flags)
        ss_t, se_t = (ss.start if ss else None), (se.end if se else None)
        rationale = None
    changed = (ss_t is not None and ss_t < (tr.by_id(start_utt).start if tr.by_id(start_utt) else 0)) or \
              (se_t is not None and se_t > (tr.by_id(end_utt).end if tr.by_id(end_utt) else 0))
    return Integrity(score=int(score), flags=flags, suggested_start=ss_t if changed else None,
                     suggested_end=se_t if changed else None, checked_with=how, rationale=rationale)
