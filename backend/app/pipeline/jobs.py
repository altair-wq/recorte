"""Job runners: source pipeline (ingest → transcribe → moments) and clip render (gated on approval)."""
from __future__ import annotations

import logging
from pathlib import Path

from .. import config, db
from ..models import Clip, Moment, PipelineError, Source, new_id
from . import endcard, ingest, manifest, moments, render, transcribe

log = logging.getLogger(__name__)


def run_source_pipeline(source_id: str, *, local_file: Path | None = None, demo: bool = False) -> Source:
    try:
        if demo:
            ingest.ingest_fixture(source_id)
        else:
            ingest.ingest(source_id, local_file=local_file)
        transcribe.transcribe(source_id, use_fixture=demo)
        moments.find_moments(source_id, use_fixture=demo)
        db.set_source_status(source_id, "ready")
    except PipelineError as e:
        log.exception("pipeline failed")
        db.set_source_status(source_id, "error", f"{e.step}: {e.message}")
    except Exception as e:
        log.exception("pipeline crashed")
        db.set_source_status(source_id, "error", str(e)[:400])
    return db.get_source(source_id)  # type: ignore[return-value]


def create_clip_record(m: Moment) -> Clip:
    """Allocate a clip id for an approved moment. Raises PermissionError if not approved."""
    if m.status != "approved" or m.review is None or m.review.decision != "approved":
        raise PermissionError("moment is not approved")
    clip = Clip(id=new_id("c"), moment_id=m.id, source_id=m.source_id, status="rendering")
    db.save_clip(clip)
    m.clip_id = clip.id
    db.save_moment(m)
    return clip


def render_clip(clip_id: str) -> Clip:
    clip = db.get_clip(clip_id)
    if clip is None:
        raise PipelineError("render", f"unknown clip {clip_id}")
    try:
        m = db.get_moment(clip.moment_id)
        src = db.get_source(clip.source_id)
        tr = db.get_transcript(clip.source_id)
        if m is None or src is None or tr is None:
            raise PipelineError("render", "moment/source/transcript missing")
        if m.status != "approved" or m.review is None:
            raise PipelineError("render", "refusing to render: moment not approved")
        out_dir = config.clip_dir(clip.id)
        captions_on = config.HAS_SUBTITLES_FILTER
        body = render.render_body(Path(src.file_path), tr, m.start, m.end, out_dir, captions_on=captions_on)
        card_png = endcard.make_endcard(headline=m.headline, speaker=m.speaker, source_title=src.title, start=m.start, end=m.end,
                                        approved_by=m.review.by, verify_url=manifest.verify_url(clip.id), out=out_dir / "endcard.png",
                                        score=m.integrity.score)
        card = render.render_endcard_video(card_png, out_dir)
        final = render.concat(body, card, out_dir / "clip.mp4")
        render.thumbnail(final, out_dir / "thumb.jpg")
        man = manifest.build_manifest(src, tr, m, clip, final, captions=captions_on)
        manifest.write_manifest(man, out_dir / "manifest.json")
        clip.file_path = str(final)
        clip.thumb_path = str(out_dir / "thumb.jpg")
        clip.manifest_path = str(out_dir / "manifest.json")
        clip.sha256 = man["render"]["sha256"]
        clip.status = "ready"
        db.save_clip(clip)
    except Exception as e:
        log.exception("render failed")
        clip.status = "error"
        clip.error = str(e)[:600]
        db.save_clip(clip)
    return clip
