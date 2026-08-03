from pathlib import Path
from types import SimpleNamespace

from meet_assistant.config import Settings, configure_process_environment
from meet_assistant.domain import MeetingMinutes, SessionCreate
from meet_assistant.jobs import ProcessingCoordinator
from meet_assistant.storage import MeetingRepository


class NoopSummarizer:
    def summarize(self, meeting_id, title, transcript):
        return MeetingMinutes(meeting_id=meeting_id, title=title, transcript=transcript)


class SuccessfulPipeline:
    def finalize(self, session_id):
        return SimpleNamespace(output_dir=Path("D:/result"))


class NoopResources:
    def set_mode(self, mode):
        pass

    def restore(self):
        pass


def test_retry_recovers_processing_manifest_left_by_helper_crash(tmp_path: Path) -> None:
    project = tmp_path / "project"
    settings = Settings(project_root=project, runtime_root=project / "runtime")
    configure_process_environment(settings)
    repository = MeetingRepository(settings)
    session = repository.create_session(SessionCreate(title="Interrupted"))
    repository.update_status(session.id, "processing")
    coordinator = ProcessingCoordinator(
        repository,
        SuccessfulPipeline(),
        NoopSummarizer(),
        resource_controller=NoopResources(),
    )

    state = coordinator.retry(session.id)

    assert state["status"] == "processing"

def test_regenerate_replaces_ai_fields_but_preserves_record_metadata(tmp_path: Path) -> None:
    project = tmp_path / "project"
    settings = Settings(project_root=project, runtime_root=project / "runtime")
    configure_process_environment(settings)
    repository = MeetingRepository(settings)
    meeting_dir = settings.meetings_dir / "2026-08-03_regenerate"
    meeting_dir.mkdir(parents=True)
    (meeting_dir / "recording.webm").write_bytes(b"audio")
    original = MeetingMinutes(
        meeting_id="meeting-id",
        title="Regenerate",
        duration_ms=1234,
        participants=["Lan"],
        summary="Cũ",
    )
    (meeting_dir / "minutes.json").write_text(original.model_dump_json(indent=2), "utf-8")

    class NewSummarizer:
        def summarize(self, meeting_id, title, transcript):
            return MeetingMinutes(meeting_id=meeting_id, title=title, summary="Mới")

    coordinator = ProcessingCoordinator(
        repository,
        SuccessfulPipeline(),
        NewSummarizer(),
        resource_controller=NoopResources(),
    )

    regenerated = coordinator.regenerate("meeting-id")

    assert regenerated.summary == "Mới"
    assert regenerated.duration_ms == 1234
    assert regenerated.participants == ["Lan"]
    assert repository.load_minutes("meeting-id").summary == "Mới"
