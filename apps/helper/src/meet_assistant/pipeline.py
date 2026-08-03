from __future__ import annotations

import os
import re
import shutil
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from .domain import MeetingMinutes
from .resources import PauseGate
from .storage import MeetingRepository
from .summarization import Summarizer, enforce_evidence_policy
from .transcription import Transcriber, merge_transcripts


class AudioFinalizer(Protocol):
    def finalize(self, session_path: Path, output_path: Path) -> None: ...


@dataclass(frozen=True)
class FinalizationResult:
    output_dir: Path
    minutes: MeetingMinutes


def _safe_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return slug[:60] or "meeting"


class FinalizationPipeline:
    def __init__(
        self,
        repository: MeetingRepository,
        *,
        audio_finalizer: AudioFinalizer,
        transcriber: Transcriber,
        summarizer: Summarizer,
        pause_gate: PauseGate | None = None,
    ) -> None:
        self.repository = repository
        self.audio_finalizer = audio_finalizer
        self.transcriber = transcriber
        self.summarizer = summarizer
        self.pause_gate = pause_gate or PauseGate()

    def _available_output_dir(self, title: str, started_at: datetime) -> Path:
        stem = f"{started_at.astimezone(UTC):%Y-%m-%d}_{_safe_slug(title)}"
        candidate = self.repository.settings.meetings_dir / stem
        suffix = 2
        while candidate.exists():
            candidate = self.repository.settings.meetings_dir / f"{stem}-{suffix}"
            suffix += 1
        return candidate

    def finalize(self, session_id: str) -> FinalizationResult:
        manifest = self.repository.update_status(session_id, "processing")
        session_path = self.repository.work_path(session_id)
        temporary_output = self.repository.settings.meetings_dir / f".{session_id}.tmp"
        if temporary_output.exists():
            shutil.rmtree(temporary_output)
        temporary_output.mkdir(parents=True)
        try:
            self.pause_gate.wait()
            self.repository.verify_chunks(session_id)
            recording_path = temporary_output / "recording.webm"
            self.audio_finalizer.finalize(session_path, recording_path)
            if not recording_path.is_file() or recording_path.stat().st_size == 0:
                raise RuntimeError("audio finalizer produced an empty recording")

            self.pause_gate.wait()
            stt_segments = self.transcriber.transcribe(session_path)
            captions = self.repository.load_captions(session_id)
            transcript = merge_transcripts(captions, stt_segments)
            self.pause_gate.wait()
            minutes = self.summarizer.summarize(session_id, manifest.title, transcript)
            participants = sorted(
                {
                    item.speaker
                    for item in transcript
                    if item.speaker and item.speaker not in {"Chưa xác định", "Tôi"}
                }
            )
            end_time = datetime.now(UTC)
            audio_duration_ms = max(
                (
                    chunk.started_at_ms + chunk.duration_ms
                    for chunks in manifest.chunks.values()
                    for chunk in chunks
                ),
                default=0,
            )
            minutes = minutes.model_copy(
                update={
                    "meeting_id": session_id,
                    "title": manifest.title,
                    "started_at": manifest.started_at,
                    "ended_at": end_time,
                    "duration_ms": max(
                        audio_duration_ms,
                        max((item.end_ms for item in transcript), default=0),
                    ),
                    "language": manifest.language,
                    "participants": participants,
                    "transcript": transcript,
                }
            )
            minutes = enforce_evidence_policy(minutes)
            minutes_path = temporary_output / "minutes.json"
            minutes_path.write_text(minutes.model_dump_json(indent=2), encoding="utf-8")
            MeetingMinutes.model_validate_json(minutes_path.read_text(encoding="utf-8"))

            self.pause_gate.wait()
            output_dir = self._available_output_dir(manifest.title, manifest.started_at)
            os.replace(temporary_output, output_dir)
            shutil.rmtree(session_path)
            return FinalizationResult(output_dir=output_dir, minutes=minutes)
        except Exception as error:
            if temporary_output.exists():
                shutil.rmtree(temporary_output, ignore_errors=True)
            self.repository.update_status(session_id, "failed", str(error))
            raise
