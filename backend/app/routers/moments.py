from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

from .. import config, db
from ..models import ApproveBody, Moment, PatchMomentBody, RejectBody, Review, now
from ..pipeline import integrity, jobs, snap

router = APIRouter(tags=["moments"])


def _get(moment_id: str) -> Moment:
    m = db.get_moment(moment_id)
    if m is None:
        raise HTTPException(404, "moment not found")
    return m


def _is_demo(source_id: str) -> bool:
    s = db.get_source(source_id)
    return bool(s and s.url is None and s.channel == "Recorte demo")


@router.get("/moments/{moment_id}")
def get_moment(moment_id: str) -> Moment:
    return _get(moment_id)


@router.patch("/moments/{moment_id}")
def patch_moment(moment_id: str, body: PatchMomentBody) -> Moment:
    """Adjust the span: re-snaps to utterance boundaries, records the adjustment, re-runs the integrity check."""
    m = _get(moment_id)
    if m.status != "candidate":
        raise HTTPException(409, "only candidate moments can be adjusted")
    tr = db.get_transcript(m.source_id)
    if tr is None:
        raise HTTPException(500, "transcript missing")
    s_utt, e_utt = m.start_utt, m.end_utt
    if body.start_utt is not None:
        s_utt = body.start_utt
    if body.end_utt is not None:
        e_utt = body.end_utt
    if body.start is not None or body.end is not None:
        s_utt2, e_utt2 = snap.snap_time_to_utts(tr, body.start if body.start is not None else m.start, body.end if body.end is not None else m.end)
        if body.start is not None:
            s_utt = s_utt2
        if body.end is not None:
            e_utt = e_utt2
    ids = [u.id for u in tr.utterances]
    s_utt = max(ids[0], min(s_utt, ids[-1]))
    e_utt = max(s_utt, min(e_utt, ids[-1]))
    start, end = snap.span_times(tr, s_utt, e_utt)
    if end - start > config.MAX_CLIP_S:
        raise HTTPException(400, f"span longer than {config.MAX_CLIP_S:.0f}s")
    if not snap.quote_is_verbatim(m.quote, tr, s_utt, e_utt):
        raise HTTPException(400, "span must still contain the quote")
    at = now().isoformat()
    by = body.by or config.EDITOR_DEFAULT_NAME
    if abs(start - m.start) > 1e-6:
        m.adjustments.append({"field": "start", "from": m.start, "to": start, "at": at, "by": by})
    if abs(end - m.end) > 1e-6:
        m.adjustments.append({"field": "end", "from": m.end, "to": end, "at": at, "by": by})
    m.start, m.end, m.start_utt, m.end_utt = start, end, s_utt, e_utt
    m.integrity = integrity.check(tr, s_utt, e_utt, use_fixture=_is_demo(m.source_id))
    return db.save_moment(m)


@router.post("/moments/{moment_id}/approve")
def approve(moment_id: str, body: ApproveBody, bg: BackgroundTasks) -> dict:
    m = _get(moment_id)
    if m.status == "approved" and m.clip_id:
        return {"clip_id": m.clip_id, "moment": m.model_dump(mode="json")}
    if m.status == "rejected":
        raise HTTPException(409, "moment was rejected")
    m.status = "approved"
    m.review = Review(decision="approved", by=body.by, at=now(), reason=body.reason, adjustments=list(m.adjustments))
    db.save_moment(m)
    clip = jobs.create_clip_record(m)
    bg.add_task(jobs.render_clip, clip.id)
    return {"clip_id": clip.id, "moment": db.get_moment(moment_id).model_dump(mode="json")}  # type: ignore[union-attr]


@router.post("/moments/{moment_id}/reject")
def reject(moment_id: str, body: RejectBody) -> Moment:
    m = _get(moment_id)
    if m.status == "approved":
        raise HTTPException(409, "moment already approved")
    if not body.reason.strip():
        raise HTTPException(400, "reason required")
    m.status = "rejected"
    m.review = Review(decision="rejected", by=body.by, at=now(), reason=body.reason, adjustments=list(m.adjustments))
    return db.save_moment(m)


@router.post("/moments/{moment_id}/render")
def render(moment_id: str, bg: BackgroundTasks) -> dict:
    """Explicit render endpoint. 409 unless the moment carries an approval event."""
    m = _get(moment_id)
    if m.status != "approved" or m.review is None or m.review.decision != "approved":
        raise HTTPException(409, "moment is not approved; render refused")
    if m.clip_id and (c := db.get_clip(m.clip_id)) and c.status != "error":
        return {"clip_id": c.id}
    clip = jobs.create_clip_record(m)
    bg.add_task(jobs.render_clip, clip.id)
    return {"clip_id": clip.id}
