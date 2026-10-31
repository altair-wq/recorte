from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from .. import config, db
from ..models import CreateSourceBody, Moment, Source, Transcript, new_id
from ..pipeline import jobs, moments

router = APIRouter(tags=["sources"])


def source_view(s: Source) -> dict:
    d = s.model_dump(mode="json")
    rel = lambda p: ("/data/" + str(Path(p).relative_to(config.DATA_DIR))) if p and Path(p).exists() else None
    d["file_url"] = rel(s.file_path)
    d["poster_url"] = rel(s.poster_path)
    return d


@router.post("/sources")
def create_source(body: CreateSourceBody, bg: BackgroundTasks) -> dict:
    if body.demo:
        if not config.fixtures_available():
            raise HTTPException(400, "demo fixtures not available; run `make fixtures`")
        sid = new_id("src")
        db.save_source(Source(id=sid, status="queued", title="Demo"))
        bg.add_task(jobs.run_source_pipeline, sid, demo=True)
        return {"id": sid, "status": "queued"}
    if not body.url:
        raise HTTPException(400, "url required")
    sid = new_id("src")
    db.save_source(Source(id=sid, url=body.url, status="queued"))
    bg.add_task(jobs.run_source_pipeline, sid)
    return {"id": sid, "status": "queued"}


@router.post("/sources/upload")
async def upload_source(bg: BackgroundTasks, file: UploadFile = File(...)) -> dict:
    sid = new_id("src")
    d = config.source_dir(sid)
    dst = d / "upload.mp4"
    with dst.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    db.save_source(Source(id=sid, status="queued", title=Path(file.filename or "upload").stem))
    bg.add_task(jobs.run_source_pipeline, sid, local_file=dst)
    return {"id": sid, "status": "queued"}


@router.get("/sources")
def list_sources() -> list[dict]:
    return [source_view(s) for s in db.list_sources()]


@router.get("/sources/{source_id}")
def get_source(source_id: str) -> dict:
    s = db.get_source(source_id)
    if s is None:
        raise HTTPException(404, "source not found")
    return source_view(s)


@router.get("/sources/{source_id}/transcript")
def get_transcript(source_id: str) -> Transcript:
    t = db.get_transcript(source_id)
    if t is None:
        raise HTTPException(404, "transcript not ready")
    return t


@router.get("/sources/{source_id}/moments")
def list_moments(source_id: str) -> list[Moment]:
    if db.get_source(source_id) is None:
        raise HTTPException(404, "source not found")
    db.index_moments(source_id)
    return db.list_moments(source_id)


@router.post("/sources/{source_id}/moments/rerun")
def rerun_moments(source_id: str, bg: BackgroundTasks) -> dict:
    s = db.get_source(source_id)
    if s is None:
        raise HTTPException(404, "source not found")
    demo = s.url is None and s.channel == "Recorte demo"

    def _run() -> None:
        try:
            moments.find_moments(source_id, force=True, use_fixture=demo)
            db.set_source_status(source_id, "ready")
        except Exception as e:  # noqa: BLE001
            db.set_source_status(source_id, "error", str(e)[:400])

    db.set_source_status(source_id, "finding_moments")
    bg.add_task(_run)
    return {"id": source_id, "status": "finding_moments"}
