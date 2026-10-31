"""CLI safety net.

    python -m scripts.run_pipeline <url|file|demo>        # ingest → transcript → moments, prints them
    python -m scripts.run_pipeline --approve <moment_id>  # approve + render a moment (same gate as the API)
    python -m scripts.run_pipeline demo --render-first    # demo source + approve + render the first candidate
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app import config, db
from app.models import Review, Source, new_id, now
from app.pipeline import jobs
from app.pipeline.compact import mmss


def approve_and_render(moment_id: str, by: str) -> str:
    m = db.get_moment(moment_id)
    if m is None:
        sys.exit(f"unknown moment {moment_id}")
    m.status = "approved"
    m.review = Review(decision="approved", by=by, at=now(), adjustments=list(m.adjustments))
    db.save_moment(m)
    clip = jobs.create_clip_record(m)
    clip = jobs.render_clip(clip.id)
    if clip.status != "ready":
        sys.exit(f"render failed: {clip.error}")
    print(f"clip {clip.id} → {clip.file_path}\nmanifest → {clip.manifest_path}\nsha256 {clip.sha256}")
    return clip.id


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="?", help="YouTube URL, local file, or 'demo'")
    ap.add_argument("--approve", metavar="MOMENT_ID")
    ap.add_argument("--render-first", action="store_true")
    ap.add_argument("--by", default=config.EDITOR_DEFAULT_NAME)
    args = ap.parse_args()

    if args.approve:
        approve_and_render(args.approve, args.by)
        return
    if not args.target:
        ap.error("target required")

    sid = new_id("src")
    demo = args.target == "demo"
    local: Path | None = None
    url: str | None = None
    if demo:
        pass
    elif Path(args.target).exists():
        local = Path(args.target).resolve()
    else:
        url = args.target
    db.save_source(Source(id=sid, url=url, title=local.stem if local else "", status="queued"))
    src = jobs.run_source_pipeline(sid, local_file=local, demo=demo)
    if src.status != "ready":
        sys.exit(f"pipeline error: {src.error}")
    ms = db.list_moments(sid)
    print(f"source {sid}: {src.title!r} {src.duration:.1f}s sha256={src.sha256[:12]}… — {len(ms)} moments")
    for m in ms:
        flags = ", ".join(f.type for f in m.integrity.flags) or "—"
        print(f"  {m.id}  {mmss(m.start)}-{mmss(m.end)}  int={m.integrity.score:3d}  n={m.newsworthiness}  {m.headline}")
        print(f"           «{m.quote}»  flags: {flags}")
    if args.render_first and ms:
        approve_and_render(ms[0].id, args.by)


if __name__ == "__main__":
    main()
