"""Render: cut + 9:16 center crop + burned captions + end card concat + thumb."""
from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

from .. import config, db
from ..models import PipelineError, Transcript
from . import captions

log = logging.getLogger(__name__)



def _run(cmd: list[str], step: str) -> None:
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True)
    db.log_call(step, (time.time() - t0) * 1000, model="ffmpeg")
    if r.returncode != 0:
        raise PipelineError(step, r.stderr[-1200:])


def _esc_filter_path(p: Path) -> str:
    # ffmpeg filter option escaping: backslash, colon, quote
    return str(p).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def render_body(source_mp4: Path, tr: Transcript, start: float, end: float, out_dir: Path, *, captions_on: bool = True) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    body = out_dir / "clip_body.mp4"
    # Scale to cover first: cropping the source directly fails for videos taller than 9:16.
    vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
    if captions_on and config.HAS_SUBTITLES_FILTER:
        captions.write_srt(tr, start, end, out_dir / "captions.srt")  # exported alongside the clip
        ass = captions.write_ass(tr, start, end, out_dir / "captions.ass")
        vf += f",subtitles={_esc_filter_path(ass)}:fontsdir={_esc_filter_path(config.FONTS_DIR)}"
    elif captions_on:
        log.warning("subtitles filter unavailable; rendering without captions")
    cmd = [config.FFMPEG, "-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(source_mp4),
           "-vf", vf, "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2", str(body)]
    _run(cmd, "render.body")
    return body


def render_endcard_video(endcard_png: Path, out_dir: Path, seconds: float = 2.0) -> Path:
    out = out_dir / "endcard.mp4"
    cmd = [config.FFMPEG, "-y", "-loop", "1", "-i", str(endcard_png), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
           "-t", f"{seconds}", "-r", "30", "-vf", "scale=1080:1920,setsar=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
           "-shortest", str(out)]
    _run(cmd, "render.endcard")
    return out


def concat(body: Path, endcard: Path, out: Path) -> Path:
    cmd = [config.FFMPEG, "-y", "-i", str(body), "-i", str(endcard), "-filter_complex",
           "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]", "-map", "[v]", "-map", "[a]",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", "-c:a", "aac", str(out)]
    _run(cmd, "render.concat")
    return out


def thumbnail(clip: Path, out: Path) -> Path:
    subprocess.run([config.FFMPEG, "-y", "-ss", "1", "-i", str(clip), "-frames:v", "1", str(out)], capture_output=True)
    return out
