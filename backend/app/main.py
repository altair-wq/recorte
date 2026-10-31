"""FastAPI app: CORS, routers, static serving of /data."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config
from .routers import chat, clips, moments, sources, verify

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("recorte")

app = FastAPI(title="Recorte", version=config.APP_VERSION)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(sources.router, prefix="/api")
app.include_router(moments.router, prefix="/api")
app.include_router(clips.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(verify.router)

app.mount("/data", StaticFiles(directory=str(config.DATA_DIR)), name="data")


@app.on_event("startup")
def _startup() -> None:
    if not config.HAS_SUBTITLES_FILTER:
        log.warning("ffmpeg build lacks the `subtitles` filter; clips will render without burned-in captions")
    if not config.ANTHROPIC_API_KEY:
        log.warning("ANTHROPIC_API_KEY missing; LLM steps fall back to fixtures / deterministic checks")
    log.info("DEMO_MODE=%s fixtures=%s", config.DEMO_MODE, config.fixtures_available())


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "version": config.APP_VERSION,
        "demo_mode": config.DEMO_MODE,
        "fixtures": config.fixtures_available(),
        "llm": bool(config.ANTHROPIC_API_KEY),
        "asr": bool(config.DEEPGRAM_API_KEY or config.ASSEMBLYAI_API_KEY or config.OPENAI_API_KEY),
        "captions": config.HAS_SUBTITLES_FILTER,
    }
