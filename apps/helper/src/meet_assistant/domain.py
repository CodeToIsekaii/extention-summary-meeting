from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, HttpUrl, field_validator

AudioSource = Literal["remote", "me"]
SessionStatus = Literal["recording", "processing", "failed", "completed"]


class SessionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    meet_url: HttpUrl | None = None
    language: str = "vi"

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title cannot be blank")
        return value


class ChunkMetadata(BaseModel):
    source: AudioSource
    sequence: int = Field(ge=0)
    started_at_ms: int = Field(ge=0)
    duration_ms: int = Field(gt=0, le=60_000)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SessionManifest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    meet_url: str | None = None
    language: str = "vi"
    status: SessionStatus = "recording"
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ended_at: datetime | None = None
    next_sequence: dict[AudioSource, int] = Field(default_factory=lambda: {"remote": 0, "me": 0})
    chunks: dict[AudioSource, list[ChunkMetadata]] = Field(
        default_factory=lambda: {"remote": [], "me": []}
    )
    error: str | None = None


class ChunkReceipt(BaseModel):
    source: AudioSource
    sequence: int
    bytes_written: int
    sha256: str


class CaptionSegment(BaseModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    speaker: str | None = None
    text: str = Field(min_length=1)

    @field_validator("speaker", "text")
    @classmethod
    def trim_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class CaptionAppendResult(BaseModel):
    accepted: int
    total: int


TranscriptSource = Literal["caption", "stt_remote", "stt_me", "hybrid"]


class TranscriptSegment(BaseModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    speaker: str | None = None
    text: str = Field(min_length=1)
    source: TranscriptSource


class Evidence(BaseModel):
    timestamp_ms: int = Field(ge=0)
    speaker: str | None = None
    quote: str = Field(min_length=1)


class ActionItem(BaseModel):
    task: str = Field(min_length=1)
    assignee: str | None = None
    deadline: str | None = None
    status: Literal["confirmed", "needs_confirmation", "completed"] = "needs_confirmation"
    evidence: list[Evidence] = Field(default_factory=list)


class MeetingMinutes(BaseModel):
    schema_version: int = 1
    meeting_id: str
    title: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_ms: int | None = None
    language: str = "vi"
    summary: str = ""
    topics: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    participants: list[str] = Field(default_factory=list)
    transcript: list[TranscriptSegment] = Field(default_factory=list)
