"""Transcribe: Deepgram → AssemblyAI → OpenAI whisper → fixture. Normalizes to Utterance[] with words."""
from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Protocol

import httpx

from .. import config, db
from ..models import PipelineError, Transcript, Utterance, Word

log = logging.getLogger(__name__)


class Transcriber(Protocol):
    name: str

    def available(self) -> bool: ...
    def transcribe(self, audio: Path, source_id: str) -> Transcript: ...


def _utterances_from_words(words: list[tuple[str, float, float, str | None]], max_gap: float = 0.8, max_words: int = 40) -> list[Utterance]:
    """Group words into utterances on sentence punctuation, speaker change or pauses."""
    utts: list[Utterance] = []
    cur: list[Word] = []
    cur_spk: str | None = None

    def flush() -> None:
        nonlocal cur
        if cur:
            utts.append(Utterance(id=len(utts), start=cur[0].start, end=cur[-1].end, speaker=cur_spk,
                                  text=" ".join(w.w for w in cur), words=cur))
            cur = []

    for w, s, e, spk in words:
        if cur and (spk != cur_spk or s - cur[-1].end > max_gap or len(cur) >= max_words):
            flush()
        cur_spk = spk
        cur.append(Word(w=w, start=s, end=e))
        if re.search(r"[.!?…]$", w) and len(cur) >= 3:
            flush()
    flush()
    return utts


class DeepgramTranscriber:
    name = "deepgram"

    def available(self) -> bool:
        return bool(config.DEEPGRAM_API_KEY)

    def _call(self, audio: Path, model: str) -> dict:
        params = {"model": model, "language": "es", "smart_format": "true", "punctuate": "true",
                  "utterances": "true", "diarize": "true"}
        with httpx.Client(timeout=600) as c:
            r = c.post("https://api.deepgram.com/v1/listen", params=params,
                       headers={"Authorization": f"Token {config.DEEPGRAM_API_KEY}", "Content-Type": "audio/mpeg"},
                       content=audio.read_bytes())
        if r.status_code >= 400:
            raise PipelineError("transcribe", f"deepgram {model}: {r.text[:300]}")
        return r.json()

    def transcribe(self, audio: Path, source_id: str) -> Transcript:
        t0 = time.time()
        model = config.ASR_MODEL
        try:
            data = self._call(audio, model)
        except PipelineError as e:
            log.warning("deepgram nova-3 failed (%s); retrying nova-2", e.message[:120])
            model = "nova-2"
            data = self._call(audio, model)
        utts: list[Utterance] = []
        for i, u in enumerate(data.get("results", {}).get("utterances", [])):
            words = [Word(w=w.get("punctuated_word") or w["word"], start=w["start"], end=w["end"]) for w in u.get("words", [])]
            spk = f"Speaker {int(u.get('speaker', 0)) + 1}" if "speaker" in u else None
            utts.append(Utterance(id=i, start=u["start"], end=u["end"], speaker=spk, text=u["transcript"], words=words))
        dur = utts[-1].end if utts else 0
        db.log_call("transcribe", (time.time() - t0) * 1000, model=f"deepgram/{model}", est_cost_usd=dur / 60 * 0.0077)
        return Transcript(source_id=source_id, language="es", asr_model=f"deepgram/{model}", utterances=utts)


class AssemblyAITranscriber:
    name = "assemblyai"

    def available(self) -> bool:
        return bool(config.ASSEMBLYAI_API_KEY)

    def transcribe(self, audio: Path, source_id: str) -> Transcript:
        t0 = time.time()
        h = {"authorization": config.ASSEMBLYAI_API_KEY or ""}
        with httpx.Client(timeout=600) as c:
            up = c.post("https://api.assemblyai.com/v2/upload", headers=h, content=audio.read_bytes()).json()
            job = c.post("https://api.assemblyai.com/v2/transcript", headers=h,
                         json={"audio_url": up["upload_url"], "language_code": "es", "speaker_labels": True, "punctuate": True}).json()
            while True:
                r = c.get(f"https://api.assemblyai.com/v2/transcript/{job['id']}", headers=h).json()
                if r["status"] in ("completed", "error"):
                    break
                time.sleep(3)
        if r["status"] == "error":
            raise PipelineError("transcribe", f"assemblyai: {r.get('error')}")
        words = [(w["text"], w["start"] / 1000, w["end"] / 1000, f"Speaker {w['speaker']}" if w.get("speaker") else None) for w in r["words"]]
        utts = _utterances_from_words(words)
        db.log_call("transcribe", (time.time() - t0) * 1000, model="assemblyai/best", est_cost_usd=(utts[-1].end if utts else 0) / 3600 * 0.37)
        return Transcript(source_id=source_id, language="es", asr_model="assemblyai/best", utterances=utts)


class WhisperTranscriber:
    name = "openai-whisper"

    def available(self) -> bool:
        return bool(config.OPENAI_API_KEY)

    def transcribe(self, audio: Path, source_id: str) -> Transcript:
        t0 = time.time()
        with httpx.Client(timeout=600) as c:
            r = c.post("https://api.openai.com/v1/audio/transcriptions",
                       headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
                       data={"model": "whisper-1", "language": "es", "response_format": "verbose_json",
                             "timestamp_granularities[]": "word"},
                       files={"file": (audio.name, audio.read_bytes(), "audio/mpeg")})
        if r.status_code >= 400:
            raise PipelineError("transcribe", f"whisper: {r.text[:300]}")
        data = r.json()
        words = [(w["word"], w["start"], w["end"], None) for w in data.get("words", [])]
        utts = _utterances_from_words(words)
        db.log_call("transcribe", (time.time() - t0) * 1000, model="openai/whisper-1", est_cost_usd=(utts[-1].end if utts else 0) / 60 * 0.006)
        return Transcript(source_id=source_id, language="es", asr_model="openai/whisper-1", utterances=utts)


class FixtureTranscriber:
    name = "fixture"

    def available(self) -> bool:
        return (config.FIXTURES_DIR / "transcript.json").exists()

    def transcribe(self, audio: Path, source_id: str) -> Transcript:
        t = Transcript.model_validate_json((config.FIXTURES_DIR / "transcript.json").read_text(encoding="utf-8"))
        t.source_id = source_id
        db.log_call("transcribe", 0, model="fixture")
        return t


CHAIN: list[Transcriber] = [DeepgramTranscriber(), AssemblyAITranscriber(), WhisperTranscriber()]


def transcribe(source_id: str, *, force: bool = False, use_fixture: bool = False) -> Transcript:
    cached = db.get_transcript(source_id)
    if cached and not force:
        return cached
    db.set_source_status(source_id, "transcribing")
    audio = config.source_dir(source_id) / "audio.mp3"
    chain: list[Transcriber] = [FixtureTranscriber()] if use_fixture else [*CHAIN, FixtureTranscriber()]
    errors: list[str] = []
    for t in chain:
        if not t.available():
            continue
        try:
            tr = t.transcribe(audio, source_id)
            if not tr.utterances:
                raise PipelineError("transcribe", f"{t.name} returned no utterances")
            db.save_transcript(tr)
            return tr
        except Exception as e:  # noqa: BLE001 — fall through the chain
            log.warning("transcriber %s failed: %s", t.name, e)
            errors.append(f"{t.name}: {e}")
    raise PipelineError("transcribe", "no transcriber available: " + "; ".join(errors) if errors else "no ASR key configured and no fixture")
