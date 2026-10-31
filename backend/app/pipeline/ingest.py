"""Ingest: yt-dlp download or local/fixture copy, probe, audio extract, sha256, poster."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path

from .. import config, db
from ..models import PipelineError, Source

log = logging.getLogger(__name__)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        [config.FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(json.loads(out)["format"]["duration"])


def _run(cmd: list[str], step: str) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise PipelineError(step, (r.stderr or r.stdout)[-800:])


def _link_or_copy(src: Path, dst: Path) -> None:
    if dst.exists():
        return
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy(src, dst)


def _download(url: str, dst: Path, step: str) -> dict:
    t0 = time.time()
    info = subprocess.run([config.YTDLP, "-J", "--no-playlist", url], capture_output=True, text=True)
    if info.returncode != 0:
        err = info.stderr
        if "Sign in to confirm" in err or "not a bot" in err:
            raise PipelineError(step, "YouTube bloquea descargas desde servidores en la nube. Descargá el video en tu computadora y subilo como archivo, o usá la fuente de demo.")
        raise PipelineError(step, f"yt-dlp metadata failed: {err[-400:]}")
    meta = json.loads(info.stdout)
    _run([config.YTDLP, "-f", "bv*[height<=720]+ba/b[height<=720]", "--merge-output-format", "mp4",
          "--no-playlist", "-o", str(dst), url], step)
    db.log_call("ingest.download", (time.time() - t0) * 1000, model="yt-dlp", url=url)
    return meta


def ingest(source_id: str, *, local_file: Path | None = None, force: bool = False) -> Source:
    """Produce data/sources/{id}/source.mp4 + audio.mp3 + poster.jpg and fill in Source fields."""
    src = db.get_source(source_id)
    if src is None:
        raise PipelineError("ingest", f"unknown source {source_id}")
    d = config.source_dir(source_id)
    video = d / "source.mp4"
    audio = d / "audio.mp3"
    poster = d / "poster.jpg"

    if force or not video.exists():
        db.set_source_status(source_id, "downloading")
        if local_file is not None:
            _link_or_copy(local_file, video)
            if src.url is None and src.title == "":
                src.title = local_file.stem
        elif src.url:
            meta = _download(src.url, video, "ingest")
            src.title = meta.get("title") or src.url
            src.channel = meta.get("channel") or meta.get("uploader")
        else:
            raise PipelineError("ingest", "no url or file")

    if force or not audio.exists():
        t0 = time.time()
        _run([config.FFMPEG, "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", str(audio)], "ingest.audio")
        db.log_call("ingest.audio", (time.time() - t0) * 1000, model="ffmpeg")
    if force or not poster.exists():
        subprocess.run([config.FFMPEG, "-y", "-ss", "10", "-i", str(video), "-frames:v", "1", str(poster)], capture_output=True)
        if not poster.exists():
            subprocess.run([config.FFMPEG, "-y", "-i", str(video), "-frames:v", "1", str(poster)], capture_output=True)

    src.file_path = str(video)
    src.audio_path = str(audio)
    src.poster_path = str(poster) if poster.exists() else None
    src.duration = probe_duration(video)
    src.sha256 = sha256_file(video)
    db.save_source(src)
    return src


def ingest_fixture(source_id: str) -> Source:
    """Demo path: copy the cached demo source without any network."""
    src = db.get_source(source_id)
    if src is None:
        raise PipelineError("ingest", f"unknown source {source_id}")
    meta_path = config.FIXTURES_DIR / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    src.title = meta.get("title") or "Demo source"
    src.channel = meta.get("channel")
    src.url = meta.get("url")
    db.save_source(src)
    d = config.source_dir(source_id)
    for name, fx in (("audio.mp3", "audio.mp3"), ("poster.jpg", "poster.jpg")):
        if (config.FIXTURES_DIR / fx).exists():
            _link_or_copy(config.FIXTURES_DIR / fx, d / name)
    return ingest(source_id, local_file=config.FIXTURES_DIR / "demo.mp4")
