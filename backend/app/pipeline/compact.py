"""Transcript → compact text for the LLM, plus chunking for long sources."""
from __future__ import annotations

from ..models import Transcript, Utterance


def mmss(t: float) -> str:
    t = max(0, int(round(t)))
    return f"{t // 60:02d}:{t % 60:02d}"


def line(u: Utterance) -> str:
    spk = u.speaker or "Speaker"
    return f"[u{u.id} {mmss(u.start)}-{mmss(u.end)}] {spk}: {u.text}"


def compact(tr: Transcript, start_utt: int | None = None, end_utt: int | None = None) -> str:
    utts = [u for u in tr.utterances if (start_utt is None or u.id >= start_utt) and (end_utt is None or u.id <= end_utt)]
    return "\n".join(line(u) for u in utts)


def chunks(tr: Transcript, window_s: float = 12 * 60, overlap_s: float = 60) -> list[str]:
    if not tr.utterances or tr.utterances[-1].end <= window_s * 1.1:
        return [compact(tr)]
    out: list[str] = []
    t0 = 0.0
    total = tr.utterances[-1].end
    while t0 < total:
        t1 = t0 + window_s
        out.append("\n".join(line(u) for u in tr.utterances if u.end > t0 and u.start < t1))
        t0 = t1 - overlap_s
    return out


def context_block(tr: Transcript, start_utt: int, end_utt: int, window_s: float = 20.0) -> str:
    """Span lines tagged IN, surrounding lines tagged CONTEXT (±window_s)."""
    s = tr.by_id(start_utt)
    e = tr.by_id(end_utt)
    if s is None or e is None:
        return compact(tr, start_utt, end_utt)
    lines = []
    for u in tr.utterances:
        if start_utt <= u.id <= end_utt:
            lines.append(f"IN      {line(u)}")
        elif u.end >= s.start - window_s and u.start <= e.end + window_s:
            lines.append(f"CONTEXT {line(u)}")
    return "\n".join(lines)
