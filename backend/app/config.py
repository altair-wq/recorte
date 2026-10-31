"""Environment, paths and feature switches. Loaded once at import."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent
load_dotenv(REPO_DIR / ".env")

DATA_DIR = Path(os.getenv("DATA_DIR", BACKEND_DIR / "data"))
SOURCES_DIR = DATA_DIR / "sources"
CLIPS_DIR = DATA_DIR / "clips"
LOGS_PATH = DATA_DIR / "logs.jsonl"
FIXTURES_DIR = BACKEND_DIR / "fixtures" / "demo"
FONTS_DIR = BACKEND_DIR / "assets" / "fonts"
PROMPTS_DIR = BACKEND_DIR / "app" / "prompts"

for _d in (SOURCES_DIR, CLIPS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

APP_VERSION = "0.1.0"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY") or None
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY") or None
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY") or None
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or None
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
DEMO_MODE = os.getenv("DEMO_MODE", "0") in ("1", "true", "True")
EDITOR_DEFAULT_NAME = os.getenv("EDITOR_DEFAULT_NAME", "editor@demo")

MOMENT_MODEL = "claude-sonnet-5-5"
INTEGRITY_MODEL = "claude-haiku-5-5"
CHAT_MODEL = "claude-sonnet-5-5"
ASR_MODEL = "nova-3"

MIN_CLIP_S = 12.0
MAX_CLIP_S = 75.0
CONTEXT_WINDOW_S = 20.0

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"
YTDLP = shutil.which("yt-dlp") or "yt-dlp"


def ffmpeg_has_subtitles() -> bool:
    try:
        out = subprocess.run([FFMPEG, "-hide_banner", "-filters"], capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return False
    return " subtitles " in out


HAS_SUBTITLES_FILTER = ffmpeg_has_subtitles()


def fixtures_available() -> bool:
    return (FIXTURES_DIR / "transcript.json").exists() and (FIXTURES_DIR / "demo.mp4").exists()


def source_dir(source_id: str) -> Path:
    d = SOURCES_DIR / source_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def clip_dir(clip_id: str) -> Path:
    d = CLIPS_DIR / clip_id
    d.mkdir(parents=True, exist_ok=True)
    return d
