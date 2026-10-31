"""Chat agent: Claude with tools (search_transcript, propose_moment). Deterministic fallback without a key."""
from __future__ import annotations

import json
import logging
import re
import time
import unicodedata

from .. import config, db
from ..models import ChatReply, Moment, Transcript
from . import compact, integrity, moments, snap

log = logging.getLogger(__name__)

TOOLS = [
    {
        "name": "search_transcript",
        "description": "Case- and accent-insensitive keyword search over the transcript utterances. Returns the top 15 hits.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "propose_moment",
        "description": "Create a candidate moment (needs editor approval). Span is whole utterances start_utt..end_utt inclusive.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_utt": {"type": "integer"}, "end_utt": {"type": "integer"},
                "headline": {"type": "string", "description": "max 80 chars"}, "why": {"type": "string"},
                "quote": {"type": "string", "description": "verbatim text copied from the span"},
            },
            "required": ["start_utt", "end_utt", "headline", "why", "quote"],
        },
    },
]


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


STOP = set(["el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al", "a", "en", "y", "o", "que", "se", "con", "por", "para", "como", "cada", "vez", "cuando", "donde", "sobre", "menciona", "mencionan", "habla", "hablan", "dice", "dicen", "encontra", "encuentra", "busca", "buscá", "encontrá", "todas", "todos", "las", "los", "veces", "tema", "me", "mostra", "mostrame", "dame", "quiero"])


def search_transcript(tr: Transcript, query: str, top: int = 15) -> list[dict]:
    q = _fold(query)
    terms = [t for t in re.findall(r"\w+", q) if t not in STOP and len(t) > 2]
    hits = []
    for u in tr.utterances:
        f = _fold(u.text)
        score = (3 if q and q in f else 0) + sum(1 for t in terms if t in f)
        if score:
            hits.append((score, {"utt_id": u.id, "start": u.start, "speaker": u.speaker, "text": u.text}))
    hits.sort(key=lambda h: (-h[0], h[1]["start"]))
    return [h[1] for h in hits[:top]]


def propose_moment(source_id: str, tr: Transcript, start_utt: int, end_utt: int, headline: str, why: str, quote: str | None = None) -> Moment | str:
    """Snap + validate + integrity → candidate with origin='chat'. Returns an error string if rejected."""
    if tr.by_id(start_utt) is None or tr.by_id(end_utt) is None:
        return "utterance ids out of range"
    if end_utt < start_utt:
        start_utt, end_utt = end_utt, start_utt
    quote = quote or (tr.by_id(start_utt).text if tr.by_id(start_utt) else "")
    s_utt, e_utt = snap.clamp_span(tr, start_utt, end_utt, quote)
    if not snap.quote_is_verbatim(quote, tr, s_utt, e_utt):
        return "quote is not verbatim transcript text"
    existing = db.list_moments(source_id)
    start, end = snap.span_times(tr, s_utt, e_utt)
    for m in existing:
        if snap.overlap_ratio((start, end), (m.start, m.end)) > 0.5 and m.status != "rejected":
            return f"overlaps existing moment {m.id}"
    raw = [{"start_utt": s_utt, "end_utt": e_utt, "headline": headline, "summary": "", "why": why, "quote": quote, "newsworthiness": 3,
            "speaker": tr.by_id(s_utt).speaker if tr.by_id(s_utt) else None}]
    ms = moments.materialize(source_id, tr, raw, origin="chat")
    if not ms:
        return "rejected by validation"
    m = ms[0]
    is_demo = (s := db.get_source(source_id)) is not None and s.url is None and s.channel == "Recorte demo"
    m.integrity = integrity.check(tr, m.start_utt, m.end_utt, use_fixture=is_demo)
    db.save_moment(m)
    db.index_moments(source_id)
    return m


# ---- fallback (no key) ---------------------------------------------------

WANTS_MOMENTS = re.compile(r"\b(encontr|busc|arm|agreg|cre|clip|moment|find|add|every|cada vez)")


def _fallback(source_id: str, tr: Transcript, query: str, lang: str) -> ChatReply:
    fixture = config.FIXTURES_DIR / "chat.json"
    canned = None
    if fixture.exists():
        try:
            for entry in json.loads(fixture.read_text(encoding="utf-8")):
                if all(k in _fold(query) for k in entry.get("match", [])):
                    canned = entry
                    break
        except Exception:  # noqa: BLE001
            canned = None
    hits = search_transcript(tr, query, top=8)
    created: list[str] = []
    lines: list[str] = []
    if not hits:
        txt = "No encontré ese tema en la transcripción." if lang == "es" else "I could not find that topic in the transcript."
        return ChatReply(reply=txt, created_moment_ids=[])
    if WANTS_MOMENTS.search(_fold(query)):
        for h in hits:
            if len(created) >= 3:
                break
            uid = h["utt_id"]
            # grow forward within the same speaker so the clip is self-contained
            e_utt = uid
            while (nxt := tr.by_id(e_utt + 1)) is not None and nxt.speaker == tr.by_id(uid).speaker and tr.by_id(e_utt).end - tr.by_id(uid).start < 14:  # type: ignore[union-attr]
                e_utt += 1
            raw_terms = [t for t in re.findall(r"\w+", query) if _fold(t) not in STOP and len(t) > 2]
            topic = raw_terms[0].lower() if raw_terms else "tema"
            headline = f"Sobre {topic}: «{h['text'][:60].rstrip('.,')}…»" if lang == "es" else f"On {topic}: “{h['text'][:60].rstrip('.,')}…”"
            res = propose_moment(source_id, tr, uid, e_utt, headline[:80], f"Mención de '{topic}' encontrada por búsqueda." if lang == "es" else f"Mention of '{topic}' found by search.", h["text"])
            if isinstance(res, Moment):
                created.append(res.id)
                lines.append(f"- [{compact.mmss(h['start'])}] {h['speaker'] or ''}: «{h['text']}» → nuevo momento {res.id} (integridad {res.integrity.score})")
            else:
                lines.append(f"- [{compact.mmss(h['start'])}] {h['speaker'] or ''}: «{h['text']}» ({res})")
    else:
        for h in hits[:6]:
            lines.append(f"- [{compact.mmss(h['start'])}] {h['speaker'] or ''}: «{h['text']}»")
    if canned and canned.get("reply"):
        head = canned["reply"]
    elif lang == "es":
        head = f"Encontré {len(hits)} menciones." + (f" Agregué {len(created)} como momentos candidatos; necesitan aprobación editorial." if created else "")
    else:
        head = f"Found {len(hits)} mentions." + (f" Added {len(created)} as candidate moments; they still need editor approval." if created else "")
    db.log_call("chat", 0, model="fallback-search")
    return ChatReply(reply=head + "\n" + "\n".join(lines), created_moment_ids=created)


# ---- Claude ---------------------------------------------------------------

def _claude(source_id: str, tr: Transcript, messages: list[dict], lang: str) -> ChatReply:
    import anthropic

    src = db.get_source(source_id)
    system = moments.load_prompt("chat_agent.md", lang="español rioplatense" if lang == "es" else "English",
                                 title=src.title if src else "", transcript=compact.compact(tr))
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    convo = [{"role": m["role"], "content": m["content"]} for m in messages][-12:]
    created: list[str] = []
    t0 = time.time()
    cost = 0.0
    for _ in range(6):
        resp = client.messages.create(model=config.CHAT_MODEL, max_tokens=1200, temperature=0.2, system=system, tools=TOOLS, messages=convo)
        cost += resp.usage.input_tokens / 1e6 * 3 + resp.usage.output_tokens / 1e6 * 15
        if resp.stop_reason != "tool_use":
            text = "".join(b.text for b in resp.content if b.type == "text")
            db.log_call("chat", (time.time() - t0) * 1000, model=config.CHAT_MODEL, est_cost_usd=cost)
            return ChatReply(reply=text, created_moment_ids=created)
        assistant_blocks: list[dict] = []
        for b in resp.content:
            if b.type == "text":
                assistant_blocks.append({"type": "text", "text": b.text})
            elif b.type == "tool_use":
                assistant_blocks.append({"type": "tool_use", "id": b.id, "name": b.name, "input": b.input})
        convo.append({"role": "assistant", "content": assistant_blocks})
        results = []
        for b in resp.content:
            if b.type != "tool_use":
                continue
            if b.name == "search_transcript":
                out = search_transcript(tr, str(b.input.get("query", "")))
            elif b.name == "propose_moment":
                res = propose_moment(source_id, tr, int(b.input["start_utt"]), int(b.input["end_utt"]), str(b.input["headline"]), str(b.input.get("why", "")), b.input.get("quote"))
                if isinstance(res, Moment):
                    created.append(res.id)
                    out = {"created": res.id, "start": res.start, "end": res.end, "integrity": res.integrity.model_dump()}
                else:
                    out = {"error": res}
            else:
                out = {"error": "unknown tool"}
            results.append({"type": "tool_result", "tool_use_id": b.id, "content": json.dumps(out, ensure_ascii=False)})
        convo.append({"role": "user", "content": results})
    db.log_call("chat", (time.time() - t0) * 1000, model=config.CHAT_MODEL, est_cost_usd=cost)
    return ChatReply(reply="(sin respuesta)", created_moment_ids=created)


def chat(source_id: str, messages: list[dict], lang: str = "es") -> ChatReply:
    tr = db.get_transcript(source_id)
    if tr is None:
        return ChatReply(reply="Transcript not ready.")
    query = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    if config.ANTHROPIC_API_KEY:
        try:
            return _claude(source_id, tr, messages, lang)
        except Exception as e:  # noqa: BLE001
            log.warning("chat LLM failed, falling back: %s", e)
    return _fallback(source_id, tr, query, lang)
