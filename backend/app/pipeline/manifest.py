"""Provenance manifest written next to the clip."""
from __future__ import annotations

import json
from pathlib import Path

from .. import config
from ..models import Clip, Moment, Source, Transcript, now
from .ingest import sha256_file


def verify_url(clip_id: str) -> str:
    return f"{config.PUBLIC_BASE_URL}/v/{clip_id}"


def build_manifest(src: Source, tr: Transcript, m: Moment, clip: Clip, clip_path: Path, *, captions: bool) -> dict:
    assert m.review is not None and m.review.decision == "approved"
    return {
        "clip_id": clip.id,
        "created_at": now().isoformat(),
        "source": {"url": src.url, "title": src.title, "channel": src.channel, "duration": src.duration, "sha256": src.sha256},
        "span": {"start": m.start, "end": m.end, "start_utt": m.start_utt, "end_utt": m.end_utt},
        "quote": m.quote,
        "speaker": m.speaker,
        "moment": {"id": m.id, "headline": m.headline, "summary": m.summary, "why": m.why, "origin": m.origin,
                   "orig_start": m.orig_start, "orig_end": m.orig_end},
        "integrity": {"score": m.integrity.score, "checked_with": m.integrity.checked_with,
                      "flags": [f.model_dump() for f in m.integrity.flags], "adjustments": m.adjustments},
        "approval": {"by": m.review.by, "at": m.review.at.isoformat(), "reason": m.review.reason},
        "pipeline": {"asr": tr.asr_model, "llm": config.MOMENT_MODEL, "integrity_llm": config.INTEGRITY_MODEL, "app_version": config.APP_VERSION},
        "render": {"aspect": "9:16", "captions": captions, "endcard": True, "sha256": sha256_file(clip_path)},
        "verify_url": verify_url(clip.id),
    }


def write_manifest(manifest: dict, path: Path) -> Path:
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
