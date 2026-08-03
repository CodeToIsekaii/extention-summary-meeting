from __future__ import annotations

from pathlib import Path

import pytest

from meet_assistant.config import Settings, configure_process_environment
from meet_assistant.domain import (
    ActionItem,
    CaptionSegment,
    Evidence,
    MeetingMinutes,
    SessionCreate,
    TranscriptSegment,
)
from meet_assistant.pipeline import FinalizationPipeline
from meet_assistant.storage import MeetingRepository, SessionNotFoundError


class FakeAudioFinalizer:
    def finalize(self, session_path: Path, output_path: Path) -> None:
        output_path.write_bytes(b"valid-webm-placeholder")


class FakeTranscriber:
    def transcribe(self, session_path: Path) -> list[TranscriptSegment]:
        return [
            TranscriptSegment(
                start_ms=1000,
                end_ms=2500,
                speaker=None,
                text="Lan sẽ gửi báo cáo vào thứ Sáu.",
                source="stt_remote",
            )
        ]


class FakeSummarizer:
    def summarize(
        self, meeting_id: str, title: str, transcript: list[TranscriptSegment]
    ) -> MeetingMinutes:
        return MeetingMinutes(
            meeting_id=meeting_id,
            title=title,
            summary="Lan sẽ gửi báo cáo.",
            transcript=transcript,
            action_items=[
                ActionItem(
                    task="Gửi báo cáo",
                    assignee="Lan",
                    deadline="2026-08-07",
                    status="confirmed",
                    evidence=[
                        Evidence(
                            timestamp_ms=1000,
                            speaker="Lan",
                            quote="Lan sẽ gửi báo cáo vào thứ Sáu.",
                        )
                    ],
                )
            ],
        )


@pytest.fixture
def repository(tmp_path: Path) -> MeetingRepository:
    project = tmp_path / "project"
    settings = Settings(project_root=project, runtime_root=project / "runtime")
    configure_process_environment(settings)
    return MeetingRepository(settings)


def test_successful_finalize_keeps_exactly_recording_and_minutes(
    repository: MeetingRepository,
) -> None:
    session = repository.create_session(SessionCreate(title="Sprint Planning"))
    repository.append_captions(
        session.id,
        [
            CaptionSegment(
                start_ms=900,
                end_ms=2600,
                speaker="Lan",
                text="Lan sẽ gửi báo cáo thứ Sáu.",
            )
        ],
    )
    pipeline = FinalizationPipeline(
        repository,
        audio_finalizer=FakeAudioFinalizer(),
        transcriber=FakeTranscriber(),
        summarizer=FakeSummarizer(),
    )

    result = pipeline.finalize(session.id)

    assert sorted(path.name for path in result.output_dir.iterdir()) == [
        "minutes.json",
        "recording.webm",
    ]
    assert result.minutes.action_items[0].evidence[0].speaker == "Lan"
    assert not repository.work_path(session.id).exists()
    with pytest.raises(SessionNotFoundError):
        repository.load_manifest(session.id)


def test_failed_finalize_keeps_recoverable_work_files(repository: MeetingRepository) -> None:
    session = repository.create_session(SessionCreate(title="Failure"))

    class FailingAudioFinalizer:
        def finalize(self, session_path: Path, output_path: Path) -> None:
            raise RuntimeError("ffmpeg failed")

    pipeline = FinalizationPipeline(
        repository,
        audio_finalizer=FailingAudioFinalizer(),
        transcriber=FakeTranscriber(),
        summarizer=FakeSummarizer(),
    )

    with pytest.raises(RuntimeError, match="ffmpeg failed"):
        pipeline.finalize(session.id)

    assert repository.work_path(session.id).is_dir()
    assert repository.load_manifest(session.id).status == "failed"
    assert repository.load_manifest(session.id).error == "ffmpeg failed"
