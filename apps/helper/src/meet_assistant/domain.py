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


class SessionManifest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    meet_url: str | None = None
    language: str = "vi"
    status: SessionStatus = "recording"
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ended_at: datetime | None = None
    next_sequence: dict[AudioSource, int] = Field(default_factory=lambda: {"remote": 0, "me": 0})
    error: str | None = None


class ChunkMetadata(BaseModel):
    source: AudioSource
    sequence: int = Field(ge=0)
    started_at_ms: int = Field(ge=0)
    duration_ms: int = Field(gt=0, le=60_000)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


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

