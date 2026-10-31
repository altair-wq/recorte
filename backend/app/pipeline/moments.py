"""Moment agent: Claude finds candidate moments; fixture fallback; snap + validate into Moment[]."""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from .. import config, db
from ..models import Integrity, Moment, PipelineError, Transcript, new_id
from . import compact, snap

log = logging.getLogger(__name__)

TOOL = {
    "name": "propose_moments",
    "description": "Return the candidate moments.",
    "input_schema": {
        "type": "object",
        "properties": {
            "moments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "start_utt": {"type": "integer"},
                        "end_utt": {"type": "integer"},
                        "headline": {"type": "string"},
                        "summary": {"type": "string"},
                        "why": {"type": "string"},
                        "quote": {"type": "string"},
                        "speaker": {"type": "string"},
                        "newsworthiness": {"type": "integer", "minimum": 1, "maximum": 5},
                    },
                    "required": ["start_utt", "end_utt", "headline", "summary", "why", "quote", "newsworthiness"],
                },
            }
        },
        "required": ["moments"],
    },
}


def load_prompt(name: str, **vars: Any) -> str:
    text = (config.PROMPTS_DIR / name).read_text(encoding="utf-8")
    for k, v in vars.items():
        text = text.replace("{{" + k + "}}", str(v))
    return text


def _claude_find(chunk: str, lang: str, duration_s: float) -> list[dict]:
    import anthropic

    hours = max(duration_s / 3600, 0.25)
    n_min, n_max = max(3, int(6 * hours)), max(6, int(10 * hours))
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    system = load_prompt("moment_finder.md", n_min=n_min, n_max=n_max, lang="español" if lang == "es" else "English")
    t0 = time.time()
    for attempt in range(2):
        resp = client.messages.create(
            model=config.MOMENT_MODEL, max_tokens=4000, temperature=0.3, system=system,
            tools=[TOOL], tool_choice={"type": "tool", "name": "propose_moments"},
            messages=[{"role": "user", "content": f"Transcript:\n\n{chunk}"}],
        )
        usage = resp.usage
        cost = usage.input_tokens / 1e6 * 3 + usage.output_tokens / 1e6 * 15
        db.log_call("moments.find", (time.time() - t0) * 1000, model=config.MOMENT_MODEL, est_cost_usd=cost,
                    input_tokens=usage.input_tokens, output_tokens=usage.output_tokens)
        for block in resp.content:
            if block.type == "tool_use" and isinstance(block.input, dict) and isinstance(block.input.get("moments"), list):
                return block.input["moments"]
        log.warning("moment agent returned no tool call (attempt %d)", attempt + 1)
    return []


def find_moments_raw(source_id: str, tr: Transcript, *, use_fixture: bool = False) -> list[dict]:
    """Raw LLM-shaped candidates (start_utt/end_utt/...). Fixture when no key or DEMO."""
    fixture = config.FIXTURES_DIR / "moments.json"
    if use_fixture or not config.ANTHROPIC_API_KEY:
        if not fixture.exists():
            raise PipelineError("moments", "no ANTHROPIC_API_KEY and no fixture moments")
        log.info("moment agent: using fixture (%s)", "demo" if use_fixture else "no API key")
        db.log_call("moments.find", 0, model="fixture")
        return json.loads(fixture.read_text(encoding="utf-8"))["moments"]
    duration = tr.utterances[-1].end if tr.utterances else 0
    raw: list[dict] = []
    chunks = compact.chunks(tr)
    for chunk in chunks:
        try:
            raw.extend(_claude_find(chunk, tr.language, duration if len(chunks) == 1 else 12 * 60))
        except Exception as e:  # noqa: BLE001 — never dead-end a source because the LLM call failed
            log.warning("moment agent failed on a chunk (%s); using heuristic candidates", e)
    if not raw:
        raw = heuristic_candidates(tr)
        db.log_call("moments.find", 0, model="heuristic")
    return raw


_SIGNAL = re.compile(r"\d|por ciento|millones|vamos a|no vamos|nunca|ning[uú]n|falso|compromet|anunci|aument|baj[aó]|prometo|garantiz", re.I)


def heuristic_candidates(tr: Transcript, max_n: int = 8) -> list[dict]:
    """No-LLM fallback: pick utterances with numbers/claims, span them with the next utterance of the same speaker."""
    scored = []
    for u in tr.utterances:
        hits = len(_SIGNAL.findall(u.text))
        if hits and len(u.text.split()) >= 6:
            scored.append((hits + min(len(u.text), 160) / 160, u))
    scored.sort(key=lambda t: -t[0])
    out: list[dict] = []
    taken: list[tuple[float, float]] = []
    for _, u in scored:
        e_utt = u.id
        nxt = tr.by_id(u.id + 1)
        if nxt is not None and nxt.speaker == u.speaker:
            e_utt = nxt.id
        start, end = u.start, (tr.by_id(e_utt) or u).end
        if any(snap.overlap_ratio((start, end), t) > 0.3 for t in taken):
            continue
        taken.append((start, end))
        out.append({"start_utt": u.id, "end_utt": e_utt, "headline": u.text[:77].rstrip(" ,.;:") + ("…" if len(u.text) > 77 else ""),
                    "summary": tr.text_between(u.id, e_utt)[:240], "why": "Afirmación con cifras o compromiso detectada automáticamente (sin LLM).",
                    "quote": u.text, "speaker": u.speaker, "newsworthiness": 3})
        if len(out) >= max_n:
            break
    return out


def materialize(source_id: str, tr: Transcript, raw: list[dict], origin: str = "agent") -> list[Moment]:
    """Snap, clamp, validate quotes, dedupe → Moment[] (integrity not yet checked)."""
    prepared: list[dict] = []
    for r in raw:
        try:
            s_utt, e_utt = int(r["start_utt"]), int(r["end_utt"])
            if tr.by_id(s_utt) is None or tr.by_id(e_utt) is None or e_utt < s_utt:
                log.warning("rejecting moment with bad utt ids %s-%s", s_utt, e_utt)
                continue
            s_utt, e_utt = snap.clamp_span(tr, s_utt, e_utt, r.get("quote"))
            if not snap.quote_is_verbatim(r.get("quote", ""), tr, s_utt, e_utt):
                log.warning("rejecting moment: quote not verbatim: %r", r.get("quote", "")[:80])
                continue
            start, end = snap.span_times(tr, s_utt, e_utt)
            prepared.append({**r, "start_utt": s_utt, "end_utt": e_utt, "start": start, "end": end})
        except Exception as e:  # noqa: BLE001
            log.warning("rejecting malformed moment %s: %s", r, e)
    prepared = snap.dedupe(prepared)
    out: list[Moment] = []
    for p in prepared:
        out.append(Moment(
            id=new_id("m"), source_id=source_id, start=p["start"], end=p["end"], orig_start=p["start"], orig_end=p["end"],
            start_utt=p["start_utt"], end_utt=p["end_utt"], headline=str(p.get("headline", ""))[:80],
            summary=str(p.get("summary", "")), why=str(p.get("why", "")), quote=snap.norm_ws(p["quote"]),
            speaker=p.get("speaker") or (tr.by_id(p["start_utt"]).speaker if tr.by_id(p["start_utt"]) else None),
            newsworthiness=int(p.get("newsworthiness", 3)), integrity=Integrity(), origin=origin,  # type: ignore[arg-type]
        ))
    return out


def find_moments(source_id: str, *, force: bool = False, use_fixture: bool = False, with_integrity: bool = True) -> list[Moment]:
    existing = db.list_moments(source_id)
    if existing and not force:
        return existing
    tr = db.get_transcript(source_id)
    if tr is None:
        raise PipelineError("moments", "transcript missing")
    db.set_source_status(source_id, "finding_moments")
    raw = find_moments_raw(source_id, tr, use_fixture=use_fixture)
    moments = materialize(source_id, tr, raw)
    if with_integrity:
        from . import integrity
        for m in moments:
            m.integrity = integrity.check(tr, m.start_utt, m.end_utt, use_fixture=use_fixture)
    db.save_moments(source_id, moments)
    db.index_moments(source_id)
    return moments
