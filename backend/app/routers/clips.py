from __future__ import annotations

import io
import json
from pathlib import Path

import qrcode
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from .. import config, db
from ..models import Clip

router = APIRouter(tags=["clips"])


def _url(p: str) -> str | None:
    if not p or not Path(p).exists():
        return None
    return "/data/" + str(Path(p).relative_to(config.DATA_DIR))


def clip_view(c: Clip) -> dict:
    d = c.model_dump(mode="json")
    d["file_url"] = _url(c.file_path)
    d["thumb_url"] = _url(c.thumb_path)
    d["manifest_url"] = _url(c.manifest_path)
    d["verify_url"] = f"{config.PUBLIC_BASE_URL}/v/{c.id}"
    m = db.get_moment(c.moment_id)
    d["moment"] = m.model_dump(mode="json") if m else None
    s = db.get_source(c.source_id)
    d["source"] = {"id": s.id, "title": s.title, "channel": s.channel, "url": s.url, "duration": s.duration} if s else None
    return d


@router.get("/clips/{clip_id}")
def get_clip(clip_id: str) -> dict:
    c = db.get_clip(clip_id)
    if c is None:
        raise HTTPException(404, "clip not found")
    return clip_view(c)


@router.get("/clips/{clip_id}/manifest")
def get_manifest(clip_id: str) -> dict:
    c = db.get_clip(clip_id)
    if c is None:
        raise HTTPException(404, "clip not found")
    if not c.manifest_path or not Path(c.manifest_path).exists():
        raise HTTPException(409, f"clip not ready ({c.status})")
    return json.loads(Path(c.manifest_path).read_text(encoding="utf-8"))


@router.get("/clips/{clip_id}/qr.png")
def get_qr(clip_id: str) -> Response:
    if db.get_clip(clip_id) is None:
        raise HTTPException(404, "clip not found")
    img = qrcode.make(f"{config.PUBLIC_BASE_URL}/v/{clip_id}", box_size=8, border=1)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(buf.getvalue(), media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})
