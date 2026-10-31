"""Boundary snapping, duration clamps, dedupe, verbatim-quote validation."""
from __future__ import annotations

import logging
import re

from .. import config
from ..models import Transcript, Utterance

log = logging.getLogger(__name__)


def norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def quote_is_verbatim(quote: str, tr: Transcript, start_utt: int, end_utt: int) -> bool:
    joined = norm_ws(tr.text_between(start_utt, end_utt))
    q = norm_ws(quote)
    return bool(q) and q in joined


def snap_time_to_utts(tr: Transcript, start: float, end: float) -> tuple[int, int]:
    """Nearest utterance boundaries to arbitrary times (editor drags)."""
    utts = tr.utterances
    s_id = min(utts, key=lambda u: abs(u.start - start)).id
    e_id = min(utts, key=lambda u: abs(u.end - end)).id
    e_id = max(e_id, s_id)
    return s_id, e_id


def clamp_span(tr: Transcript, start_utt: int, end_utt: int, quote: str | None = None) -> tuple[int, int]:
    """Clamp [start_utt, end_utt] to MIN/MAX_CLIP_S by trimming edges, keeping the quote's utterances."""
    ids = [u.id for u in tr.utterances]
    start_utt = max(min(start_utt, ids[-1]), ids[0])
    end_utt = max(min(end_utt, ids[-1]), start_utt)
    by = {u.id: u for u in tr.utterances}

    def dur(a: int, b: int) -> float:
        return by[b].end - by[a].start

    # which utterances contain the quote (must be kept)
    keep_lo, keep_hi = start_utt, end_utt
    if quote:
        q = norm_ws(quote)
        hits = [i for i in range(start_utt, end_utt + 1) if q in norm_ws(by[i].text)]
        if not hits:  # quote spans several utterances: find the minimal window containing it
            for a in range(start_utt, end_utt + 1):
                for b in range(a, end_utt + 1):
                    if q in norm_ws(tr.text_between(a, b)):
                        hits = list(range(a, b + 1))
                        break
                if hits:
                    break
        if hits:
            keep_lo, keep_hi = hits[0], hits[-1]

    # too long: trim the edge farther from the quote
    while dur(start_utt, end_utt) > config.MAX_CLIP_S and (start_utt < keep_lo or end_utt > keep_hi):
        if start_utt < keep_lo and (end_utt == keep_hi or (keep_lo - start_utt) >= (end_utt - keep_hi)):
            start_utt += 1
        else:
            end_utt -= 1
    # too short: extend forward then backward
    while dur(start_utt, end_utt) < config.MIN_CLIP_S and (end_utt < ids[-1] or start_utt > ids[0]):
        if end_utt < ids[-1]:
            end_utt += 1
        else:
            start_utt -= 1
    return start_utt, end_utt


def overlap_ratio(a: tuple[float, float], b: tuple[float, float]) -> float:
    inter = max(0.0, min(a[1], b[1]) - max(a[0], b[0]))
    shorter = max(1e-6, min(a[1] - a[0], b[1] - b[0]))
    return inter / shorter


def dedupe(items: list[dict], key_start: str = "start", key_end: str = "end", threshold: float = 0.5) -> list[dict]:
    kept: list[dict] = []
    for m in sorted(items, key=lambda m: -int(m.get("newsworthiness", 3))):
        if any(overlap_ratio((m[key_start], m[key_end]), (k[key_start], k[key_end])) > threshold for k in kept):
            continue
        kept.append(m)
    return sorted(kept, key=lambda m: m[key_start])


def span_times(tr: Transcript, start_utt: int, end_utt: int) -> tuple[float, float]:
    s: Utterance | None = tr.by_id(start_utt)
    e: Utterance | None = tr.by_id(end_utt)
    if s is None or e is None:
        raise ValueError(f"utterance ids out of range: {start_utt}-{end_utt}")
    return s.start, e.end


def on_boundaries(tr: Transcript, start: float, end: float, tol: float = 0.02) -> bool:
    starts = {round(u.start, 2) for u in tr.utterances}
    ends = {round(u.end, 2) for u in tr.utterances}
    return any(abs(start - s) <= tol for s in starts) and any(abs(end - e) <= tol for e in ends)
