"""Pydantic models shared by the pipeline, the API and files on disk."""
from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

SourceStatus = Literal["queued", "downloading", "transcribing", "finding_moments", "ready", "error"]
MomentStatus = Literal["candidate", "approved", "rejected"]
ClipStatus = Literal["rendering", "ready", "error"]
FlagType = Literal[
    "mid_sentence_cut",
    "missing_qualifier",
    "missing_attribution",
    "question_without_answer",
    "hypothetical_or_sarcasm",
    "needs_prior_context",
    "speaker_change_at_edge",
]


def now() -> datetime:
    return datetime.now(UTC).astimezone()


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(4)}"


class PipelineError(Exception):
    def __init__(self, step: str, message: str):
        super().__init__(f"{step}: {message}")
        self.step = step
        self.message = message


class Word(BaseModel):
    w: str
    start: float
    end: float


class Utterance(BaseModel):
    id: int
    start: float
    end: float
    speaker: str | None = None
    text: str
    words: list[Word] = Field(default_factory=list)


class Source(BaseModel):
    id: str
    url: str | None = None
    title: str = ""
    channel: str | None = None
    duration: float = 0.0
    file_path: str = ""
    audio_path: str | None = None
    poster_path: str | None = None
    sha256: str = ""
    status: SourceStatus = "queued"
    error: str | None = None
    created_at: datetime = Field(default_factory=now)
    moment_count: int = 0
    approved_count: int = 0


class Transcript(BaseModel):
    source_id: str
    language: str = "es"
    asr_model: str
    utterances: list[Utterance]

    def text_between(self, start_utt: int, end_utt: int) -> str:
        return " ".join(u.text for u in self.utterances if start_utt <= u.id <= end_utt)

    def by_id(self, utt_id: int) -> Utterance | None:
        for u in self.utterances:
            if u.id == utt_id:
                return u
        return None


class Flag(BaseModel):
    type: FlagType
    evidence: str
    at: float
    suggestion: str | None = None


class Integrity(BaseModel):
    score: int = 50
    flags: list[Flag] = Field(default_factory=list)
    suggested_start: float | None = None
    suggested_end: float | None = None
    checked_with: str = "none"
    rationale: str | None = None


class Review(BaseModel):
    decision: Literal["approved", "rejected"]
    by: str
    at: datetime = Field(default_factory=now)
    reason: str | None = None
    adjustments: list[dict[str, Any]] = Field(default_factory=list)


class Moment(BaseModel):
    id: str
    source_id: str
    start: float
    end: float
    orig_start: float
    orig_end: float
    start_utt: int
    end_utt: int
    headline: str
    summary: str = ""
    why: str = ""
    quote: str
    speaker: str | None = None
    newsworthiness: int = 3
    integrity: Integrity = Field(default_factory=Integrity)
    status: MomentStatus = "candidate"
    review: Review | None = None
    origin: Literal["agent", "chat", "manual"] = "agent"
    adjustments: list[dict[str, Any]] = Field(default_factory=list)
    clip_id: str | None = None
    created_at: datetime = Field(default_factory=now)


class Clip(BaseModel):
    id: str
    moment_id: str
    source_id: str
    file_path: str = ""
    thumb_path: str = ""
    manifest_path: str = ""
    sha256: str = ""
    status: ClipStatus = "rendering"
    error: str | None = None
    created_at: datetime = Field(default_factory=now)


# ---- API payloads -------------------------------------------------------

class CreateSourceBody(BaseModel):
    url: str | None = None
    demo: bool = False


class PatchMomentBody(BaseModel):
    start: float | None = None
    end: float | None = None
    start_utt: int | None = None
    end_utt: int | None = None
    by: str | None = None


class ApproveBody(BaseModel):
    by: str
    reason: str | None = None


class RejectBody(BaseModel):
    by: str
    reason: str


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatBody(BaseModel):
    messages: list[ChatMessage]
    lang: str = "es"


class ChatReply(BaseModel):
    reply: str
    created_moment_ids: list[str] = Field(default_factory=list)
