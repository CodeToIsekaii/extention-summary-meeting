from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from .config import Settings
from .domain import (
    CaptionAppendResult,
    CaptionSegment,
    ChunkMetadata,
    ChunkReceipt,
    MeetingMinutes,
    ProcessingStage,
    SessionCreate,
    SessionManifest,
    SessionStatus,
)
from .summarization import enforce_evidence_policy


class SessionNotFoundError(KeyError):
    pass


class ChunkConflictError(ValueError):
    pass


class MeetingRepository:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def work_path(self, session_id: str) -> Path:
        return self.settings.work_dir / session_id

    def _manifest_path(self, session_id: str) -> Path:
        return self.work_path(session_id) / "manifest.json"

    @staticmethod
    def _atomic_json(path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        os.replace(temporary, path)

    def create_session(self, request: SessionCreate) -> SessionManifest:
        manifest = SessionManifest(
            title=request.title,
            meet_url=str(request.meet_url) if request.meet_url else None,
            language=request.language,
        )
        session_path = self.work_path(manifest.id)
        (session_path / "chunks" / "remote").mkdir(parents=True, exist_ok=False)
        (session_path / "chunks" / "me").mkdir(parents=True, exist_ok=False)
        self._atomic_json(self._manifest_path(manifest.id), manifest.model_dump(mode="json"))
        self._atomic_json(session_path / "captions.json", [])
        return manifest

    def load_manifest(self, session_id: str) -> SessionManifest:
        path = self._manifest_path(session_id)
        if not path.is_file():
            raise SessionNotFoundError(session_id)
        return SessionManifest.model_validate_json(path.read_text(encoding="utf-8"))

    def _save_manifest(self, manifest: SessionManifest) -> None:
        self._atomic_json(self._manifest_path(manifest.id), manifest.model_dump(mode="json"))

    def expected_sequence(self, session_id: str, source: str) -> int:
        return self.load_manifest(session_id).next_sequence[source]  # type: ignore[index]

    def append_chunk(
        self, session_id: str, metadata: ChunkMetadata, payload: bytes
    ) -> ChunkReceipt:
        manifest = self.load_manifest(session_id)
        expected = manifest.next_sequence[metadata.source]
        actual_checksum = sha256(payload).hexdigest()
        if actual_checksum != metadata.sha256:
            raise ChunkConflictError("chunk checksum does not match payload")
        target = (
            self.work_path(session_id)
            / "chunks"
            / metadata.source
            / f"{metadata.sequence:08d}.webm"
        )
        if metadata.sequence < expected:
            existing = next(
                (
                    item
                    for item in manifest.chunks[metadata.source]
                    if item.sequence == metadata.sequence
                ),
                None,
            )
            if (
                existing is not None
                and existing.sha256 == actual_checksum
                and target.is_file()
                and sha256(target.read_bytes()).hexdigest() == actual_checksum
            ):
                return ChunkReceipt(
                    source=metadata.source,
                    sequence=metadata.sequence,
                    bytes_written=len(payload),
                    sha256=actual_checksum,
                )
            raise ChunkConflictError("duplicate chunk does not match stored payload")
        if metadata.sequence > expected:
            raise ChunkConflictError(f"expected sequence {expected}, got {metadata.sequence}")
        temporary = target.with_suffix(".webm.tmp")
        temporary.write_bytes(payload)
        os.replace(temporary, target)
        manifest.next_sequence[metadata.source] = expected + 1
        manifest.chunks[metadata.source].append(metadata)
        self._save_manifest(manifest)
        return ChunkReceipt(
            source=metadata.source,
            sequence=metadata.sequence,
            bytes_written=len(payload),
            sha256=actual_checksum,
        )

    def verify_chunks(self, session_id: str) -> None:
        manifest = self.load_manifest(session_id)
        for source in ("remote", "me"):
            expected = manifest.chunks[source]
            if [item.sequence for item in expected] != list(range(len(expected))):
                raise ChunkConflictError(f"{source} chunk sequence is incomplete")
            source_dir = self.work_path(session_id) / "chunks" / source
            files = sorted(source_dir.glob("*.webm"))
            expected_names = [f"{item.sequence:08d}.webm" for item in expected]
            if [item.name for item in files] != expected_names:
                raise ChunkConflictError(f"{source} chunk files do not match manifest")
            for metadata, path in zip(expected, files, strict=True):
                if sha256(path.read_bytes()).hexdigest() != metadata.sha256:
                    raise ChunkConflictError(
                        f"{source} chunk {metadata.sequence} checksum mismatch"
                    )

    def load_captions(self, session_id: str) -> list[CaptionSegment]:
        self.load_manifest(session_id)
        data = json.loads((self.work_path(session_id) / "captions.json").read_text("utf-8"))
        return [CaptionSegment.model_validate(item) for item in data]

    def append_captions(
        self, session_id: str, captions: list[CaptionSegment]
    ) -> CaptionAppendResult:
        existing = self.load_captions(session_id)
        fingerprints = {(item.start_ms, item.end_ms, item.speaker, item.text) for item in existing}
        accepted = 0
        for caption in captions:
            fingerprint = (caption.start_ms, caption.end_ms, caption.speaker, caption.text)
            if fingerprint not in fingerprints:
                existing.append(caption)
                fingerprints.add(fingerprint)
                accepted += 1
        existing.sort(key=lambda item: (item.start_ms, item.end_ms))
        self._atomic_json(
            self.work_path(session_id) / "captions.json",
            [caption.model_dump(mode="json") for caption in existing],
        )
        return CaptionAppendResult(accepted=accepted, total=len(existing))

    def update_status(
        self, session_id: str, status: SessionStatus, error: str | None = None
    ) -> SessionManifest:
        manifest = self.load_manifest(session_id)
        manifest.status = status
        manifest.error = error
        if status in {"failed", "completed"}:
            manifest.ended_at = datetime.now(UTC)
        self._save_manifest(manifest)
        return manifest

    def update_processing(
        self,
        session_id: str,
        stage: ProcessingStage,
        progress: int,
        error: str | None = None,
    ) -> SessionManifest:
        manifest = self.load_manifest(session_id)
        manifest.status = "processing"
        manifest.processing_stage = stage
        manifest.processing_progress = max(0, min(100, progress))
        manifest.error = error
        self._save_manifest(manifest)
        return manifest

    def list_recoverable(self) -> list[SessionManifest]:
        manifests: list[SessionManifest] = []
        if not self.settings.work_dir.exists():
            return manifests
        for manifest_path in self.settings.work_dir.glob("*/manifest.json"):
            try:
                manifest = SessionManifest.model_validate_json(
                    manifest_path.read_text(encoding="utf-8")
                )
            except (OSError, ValueError):
                continue
            if manifest.status != "completed":
                manifests.append(manifest)
        return sorted(manifests, key=lambda item: item.started_at)

    def _find_minutes_path(self, session_id: str) -> Path:
        for path in self.settings.meetings_dir.glob("*/minutes.json"):
            try:
                value = MeetingMinutes.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if value.meeting_id == session_id:
                return path
        raise SessionNotFoundError(session_id)

    def load_minutes(self, session_id: str) -> MeetingMinutes:
        path = self._find_minutes_path(session_id)
        return MeetingMinutes.model_validate_json(path.read_text(encoding="utf-8"))

    def update_minutes(self, session_id: str, patch: dict[str, Any]) -> MeetingMinutes:
        path = self._find_minutes_path(session_id)
        current = MeetingMinutes.model_validate_json(path.read_text(encoding="utf-8"))
        mutable = current.model_dump(mode="json")
        mutable.update({key: value for key, value in patch.items() if key != "meeting_id"})
        mutable["meeting_id"] = session_id
        updated = enforce_evidence_policy(MeetingMinutes.model_validate(mutable))
        self._atomic_json(path, updated.model_dump(mode="json"))
        return updated

    def recording_path(self, session_id: str) -> Path:
        path = self._find_minutes_path(session_id).parent / "recording.webm"
        if not path.is_file():
            raise SessionNotFoundError(session_id)
        return path

    def delete_recoverable(self, session_id: str) -> None:
        self.load_manifest(session_id)
        target = self.work_path(session_id).resolve()
        if not target.is_relative_to(self.settings.work_dir.resolve()):
            raise ValueError("session path escaped work directory")
        shutil.rmtree(target)
