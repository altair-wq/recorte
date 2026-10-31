from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from .. import db
from ..models import ChatBody, ChatReply
from ..pipeline import agent

router = APIRouter(tags=["chat"])


@router.post("/sources/{source_id}/chat")
async def chat(source_id: str, body: ChatBody) -> ChatReply:
    if db.get_source(source_id) is None:
        raise HTTPException(404, "source not found")
    if db.get_transcript(source_id) is None:
        raise HTTPException(409, "transcript not ready")
    return await run_in_threadpool(agent.chat, source_id, [m.model_dump() for m in body.messages], body.lang)
