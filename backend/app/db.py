"""Tiny JSON-file store. One file per record under data/. Good enough for a demo."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from . import config
from .models import Clip, Moment, Source, Transcript

T = TypeVar("T", bound=BaseModel)
_lock = threading.RLock()


def _write(path: Path, model: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(model.model_dump_json(indent=2), encoding="utf-8")
    tmp.replace(path)


def _read(path: Path, cls: type[T]) -> T | None:
    if not path.exists():
        return None
    return cls.model_validate_json(path.read_text(encoding="utf-8"))


# ---- sources ------------------------------------------------------------

def save_source(s: Source) -> Source:
    with _lock:
        _write(config.source_dir(s.id) / "source.json", s)
    return s


def get_source(source_id: str) -> Source | None:
    return _read(config.SOURCES_DIR / source_id / "source.json", Source)


def list_sources() -> list[Source]:
    out = [s for p in config.SOURCES_DIR.glob("*/source.json") if (s := _read(p, Source))]
    return sorted(out, key=lambda s: s.created_at, reverse=True)


def set_source_status(source_id: str, status: str, error: str | None = None) -> None:
    with _lock:
        s = get_source(source_id)
        if s is None:
            return
        s.status = status  # type: ignore[assignment]
        s.error = error
        save_source(s)


# ---- transcripts --------------------------------------------------------

def save_transcript(t: Transcript) -> None:
    _write(config.source_dir(t.source_id) / "transcript.json", t)


def get_transcript(source_id: str) -> Transcript | None:
    return _read(config.SOURCES_DIR / source_id / "transcript.json", Transcript)


# ---- moments ------------------------------------------------------------

def _moments_path(source_id: str) -> Path:
    return config.source_dir(source_id) / "moments.json"


def list_moments(source_id: str) -> list[Moment]:
    p = _moments_path(source_id)
    if not p.exists():
        return []
    raw = json.loads(p.read_text(encoding="utf-8"))
    items = raw["moments"] if isinstance(raw, dict) else raw
    return sorted((Moment.model_validate(m) for m in items), key=lambda m: m.start)


def save_moments(source_id: str, moments: list[Moment]) -> None:
    with _lock:
        p = _moments_path(source_id)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"moments": [m.model_dump(mode="json") for m in moments]}, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)
        s = get_source(source_id)
        if s:
            s.moment_count = len(moments)
            s.approved_count = sum(1 for m in moments if m.status == "approved")
            save_source(s)


def get_moment(moment_id: str) -> Moment | None:
    idx = _moment_index()
    sid = idx.get(moment_id)
    if sid:
        for m in list_moments(sid):
            if m.id == moment_id:
                return m
    for sid_dir in config.SOURCES_DIR.iterdir():
        for m in list_moments(sid_dir.name):
            if m.id == moment_id:
                return m
    return None


def save_moment(m: Moment) -> Moment:
    with _lock:
        ms = list_moments(m.source_id)
        ms = [x for x in ms if x.id != m.id] + [m]
        save_moments(m.source_id, ms)
    return m


_index_cache: dict[str, str] = {}


def _moment_index() -> dict[str, str]:
    return _index_cache


def index_moments(source_id: str) -> None:
    for m in list_moments(source_id):
        _index_cache[m.id] = source_id


# ---- clips --------------------------------------------------------------

def save_clip(c: Clip) -> Clip:
    with _lock:
        _write(config.clip_dir(c.id) / "clip.json", c)
    return c


def get_clip(clip_id: str) -> Clip | None:
    return _read(config.CLIPS_DIR / clip_id / "clip.json", Clip)


# ---- logs ---------------------------------------------------------------

def log_call(step: str, duration_ms: float, model: str | None = None, est_cost_usd: float = 0.0, **extra) -> None:
    rec = {"ts": time.time(), "step": step, "duration_ms": round(duration_ms, 1), "model": model, "est_cost_usd": round(est_cost_usd, 5), **extra}
    with _lock:
        config.LOGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with config.LOGS_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
