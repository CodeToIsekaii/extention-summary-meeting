from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path

import pytest

from meet_assistant.config import Settings, configure_process_environment
from meet_assistant.domain import CaptionSegment, ChunkMetadata, SessionCreate
from meet_assistant.storage import ChunkConflictError, MeetingRepository


@pytest.fixture
def repository(tmp_path: Path) -> MeetingRepository:
    project = tmp_path / "project"
    settings = Settings(project_root=project, runtime_root=project / "runtime")
    configure_process_environment(settings)
    return MeetingRepository(settings)


def test_create_session_writes_recoverable_manifest(repository: MeetingRepository) -> None:
    session = repository.create_session(
        SessionCreate(title="Sprint review", meet_url="https://meet.google.com/abc-defg-hij")
    )

    manifest = repository.load_manifest(session.id)

    assert manifest.id == session.id
    assert manifest.title == "Sprint review"
    assert manifest.status == "recording"
    assert (repository.work_path(session.id) / "manifest.json").is_file()


def test_append_chunk_checks_checksum_and_sequence(repository: MeetingRepository) -> None:
    session = repository.create_session(SessionCreate(title="Daily"))
    payload = b"first-audio-chunk"
    metadata = ChunkMetadata(
        source="remote",
        sequence=0,
        started_at_ms=0,
        duration_ms=5000,
        sha256=sha256(payload).hexdigest(),
    )

    receipt = repository.append_chunk(session.id, metadata, payload)

    assert receipt.sequence == 0
    assert receipt.bytes_written == len(payload)
    assert repository.expected_sequence(session.id, "remote") == 1

    duplicate = repository.append_chunk(session.id, metadata, payload)
    assert duplicate.sequence == 0
    assert repository.expected_sequence(session.id, "remote") == 1

    different = metadata.model_copy(update={"sha256": sha256(b"different").hexdigest()})
    with pytest.raises(ChunkConflictError, match="does not match stored payload"):
        repository.append_chunk(session.id, different, b"different")


def test_append_chunk_rejects_corrupt_payload(repository: MeetingRepository) -> None:
    session = repository.create_session(SessionCreate(title="Daily"))
    metadata = ChunkMetadata(
        source="me",
        sequence=0,
        started_at_ms=0,
        duration_ms=5000,
        sha256="0" * 64,
    )

    with pytest.raises(ChunkConflictError, match="checksum"):
        repository.append_chunk(session.id, metadata, b"corrupt")


def test_append_chunks_from_two_tracks_preserves_both_manifest_updates(
    repository: MeetingRepository,
) -> None:
    session = repository.create_session(SessionCreate(title="Concurrent tracks"))
    payloads = {"remote": b"remote-audio", "me": b"microphone-audio"}

    def upload(source: str):
        payload = payloads[source]
        return repository.append_chunk(
            session.id,
            ChunkMetadata(
                source=source, sequence=0, started_at_ms=0, duration_ms=30000,
                sha256=sha256(payload).hexdigest(),
            ),
            payload,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        receipts = list(executor.map(upload, payloads))

    assert {receipt.source for receipt in receipts} == {"remote", "me"}
    assert repository.expected_sequence(session.id, "remote") == 1
    assert repository.expected_sequence(session.id, "me") == 1


def test_finalize_verification_detects_chunk_corrupted_after_upload(
    repository: MeetingRepository,
) -> None:
    session = repository.create_session(SessionCreate(title="Recovery integrity"))
    payload = b"valid-on-upload"
    repository.append_chunk(
        session.id,
        ChunkMetadata(
            source="remote",
            sequence=0,
            started_at_ms=0,
            duration_ms=5000,
            sha256=sha256(payload).hexdigest(),
        ),
        payload,
    )
    chunk = repository.work_path(session.id) / "chunks" / "remote" / "00000000.webm"
    chunk.write_bytes(b"damaged-later")

    with pytest.raises(ChunkConflictError, match="checksum mismatch"):
        repository.verify_chunks(session.id)


def test_append_captions_deduplicates_identical_observer_events(
    repository: MeetingRepository,
) -> None:
    session = repository.create_session(SessionCreate(title="Planning"))
    caption = CaptionSegment(
        start_ms=1200,
        end_ms=2500,
        speaker="Lan",
        text="Hoàn thành bản thiết kế vào thứ Sáu.",
    )

    first = repository.append_captions(session.id, [caption])
    second = repository.append_captions(session.id, [caption])

    assert first.accepted == 1
    assert second.accepted == 0
    assert repository.load_captions(session.id) == [caption]


def test_list_recoverable_excludes_completed_sessions(repository: MeetingRepository) -> None:
    active = repository.create_session(SessionCreate(title="Recover me"))
    completed = repository.create_session(SessionCreate(title="Done"))
    repository.update_status(completed.id, "completed")

    recoverable = repository.list_recoverable()

    assert [item.id for item in recoverable] == [active.id]
