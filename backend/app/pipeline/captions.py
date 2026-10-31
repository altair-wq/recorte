"""Words → captions. Groups of ≤ 4 words or ≤ 1.6 s, break at punctuation. Timestamps offset by clip start.

We burn ASS (explicit 1080x1920 PlayRes so margins/sizes are in output pixels) and also write SRT for export.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..models import Transcript, Word


def _srt_ts(t: float) -> str:
    t = max(0.0, t)
    ms = round((t - int(t)) * 1000)
    s = int(t)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d},{ms:03d}"


def _ass_ts(t: float) -> str:
    t = max(0.0, t)
    cs = round((t - int(t)) * 100)
    s = int(t)
    return f"{s // 3600:d}:{(s % 3600) // 60:02d}:{s % 60:02d}.{cs:02d}"


def words_in_span(tr: Transcript, start: float, end: float) -> list[Word]:
    out: list[Word] = []
    for u in tr.utterances:
        if u.end < start or u.start > end:
            continue
        for w in u.words:
            if w.start >= start - 0.05 and w.end <= end + 0.05:
                out.append(w)
    return out


def group_words(words: list[Word], max_words: int = 4, max_s: float = 1.6) -> list[list[Word]]:
    groups: list[list[Word]] = []
    cur: list[Word] = []
    for w in words:
        if cur and (len(cur) >= max_words or w.end - cur[0].start > max_s):
            groups.append(cur)
            cur = []
        cur.append(w)
        if re.search(r"[.!?…,;:]$", w.w) and len(cur) >= 2:
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    return groups


def _cues(tr: Transcript, start: float, end: float) -> list[tuple[float, float, str]]:
    groups = group_words(words_in_span(tr, start, end))
    cues: list[tuple[float, float, str]] = []
    for i, g in enumerate(groups):
        s = g[0].start - start
        e = max(g[-1].end - start, s + 0.3)
        if i + 1 < len(groups):
            nxt = groups[i + 1][0].start - start - 0.01
            if nxt > s:
                e = min(e, nxt)
        cues.append((s, e, " ".join(w.w for w in g)))
    return cues


def build_srt(tr: Transcript, start: float, end: float) -> str:
    lines: list[str] = []
    for i, (s, e, text) in enumerate(_cues(tr, start, end), 1):
        lines += [str(i), f"{_srt_ts(s)} --> {_srt_ts(e)}", text, ""]
    return "\n".join(lines)


ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Inter,64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,0,2,60,60,420,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def build_ass(tr: Transcript, start: float, end: float) -> str:
    out = [ASS_HEADER]
    for s, e, text in _cues(tr, start, end):
        safe = text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")
        out.append(f"Dialogue: 0,{_ass_ts(s)},{_ass_ts(e)},Default,,0,0,0,,{safe}")
    return "\n".join(out) + "\n"


def write_srt(tr: Transcript, start: float, end: float, path: Path) -> Path:
    path.write_text(build_srt(tr, start, end), encoding="utf-8")
    return path


def write_ass(tr: Transcript, start: float, end: float, path: Path) -> Path:
    path.write_text(build_ass(tr, start, end), encoding="utf-8")
    return path
