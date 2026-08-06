from hashlib import sha256
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from meet_assistant.api import create_app
from meet_assistant.config import Settings, configure_process_environment
from meet_assistant.domain import MeetingMinutes


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    project = tmp_path / "project"
    value = Settings(
        project_root=project,
        runtime_root=project / "runtime",
        auth_token="test-secret",
    )
    configure_process_environment(value)
    return value


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))


@pytest.fixture
def auth() -> dict[str, str]:
    return {"Authorization": "Bearer test-secret"}


def test_health_is_public_and_reports_disk_state(client: TestClient) -> None:
    response = client.get("/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["disk"]["can_start"] is True


def test_pairing_token_is_public_for_loopback_bootstrap(client: TestClient) -> None:
    response = client.get("/v1/pairing")

    assert response.status_code == 200
    assert response.json() == {"auth_token": "test-secret"}


def test_session_routes_require_exact_bearer_token(client: TestClient) -> None:
    missing = client.post("/v1/sessions", json={"title": "Private meeting"})
    wrong = client.post(
        "/v1/sessions",
        json={"title": "Private meeting"},
        headers={"Authorization": "Bearer wrong"},
    )

    assert missing.status_code == 401
    assert wrong.status_code == 401


def test_create_session_refuses_when_start_space_threshold_is_not_met(
    settings: Settings, auth: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "free_space_gb", lambda: 4.0)
    client = TestClient(create_app(settings))

    response = client.post("/v1/sessions", json={"title": "No space"}, headers=auth)

    assert response.status_code == 507
    assert response.json()["detail"]["code"] == "insufficient_disk_space"


def test_create_upload_caption_and_list_recoverable_sessions(
    client: TestClient, auth: dict[str, str]
) -> None:
    created = client.post(
        "/v1/sessions",
        json={"title": "Sprint planning", "language": "vi"},
        headers=auth,
    )
    assert created.status_code == 201
    session_id = created.json()["id"]

    payload = b"webm-audio"
    chunk = client.post(
        f"/v1/sessions/{session_id}/chunks",
        headers=auth,
        data={
            "source": "remote",
            "sequence": "0",
            "started_at_ms": "0",
            "duration_ms": "5000",
            "sha256_hex": sha256(payload).hexdigest(),
        },
        files={"audio": ("chunk.webm", payload, "audio/webm")},
    )
    assert chunk.status_code == 201
    assert chunk.json()["bytes_written"] == len(payload)

    captions = client.post(
        f"/v1/sessions/{session_id}/captions",
        headers=auth,
        json=[
            {
                "start_ms": 500,
                "end_ms": 1400,
                "speaker": "Minh",
                "text": "Chốt deadline vào thứ Sáu.",
            }
        ],
    )
    assert captions.status_code == 200
    assert captions.json() == {"accepted": 1, "total": 1}

    recoverable = client.get("/v1/sessions", headers=auth)
    assert recoverable.status_code == 200
    assert [item["id"] for item in recoverable.json()] == [session_id]


def test_chunk_conflict_returns_stable_error_code(client: TestClient, auth: dict[str, str]) -> None:
    session_id = client.post("/v1/sessions", json={"title": "Conflict"}, headers=auth).json()["id"]
    payload = b"audio"
    fields = {
        "source": "me",
        "sequence": "1",
        "started_at_ms": "0",
        "duration_ms": "5000",
        "sha256_hex": sha256(payload).hexdigest(),
    }

    response = client.post(
        f"/v1/sessions/{session_id}/chunks",
        headers=auth,
        data=fields,
        files={"audio": ("chunk.webm", payload, "audio/webm")},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "chunk_conflict"


def test_chunk_source_must_be_one_of_the_two_recording_tracks(
    client: TestClient, auth: dict[str, str]
) -> None:
    session_id = client.post("/v1/sessions", json={"title": "Invalid source"}, headers=auth).json()[
        "id"
    ]
    payload = b"audio"

    response = client.post(
        f"/v1/sessions/{session_id}/chunks",
        headers=auth,
        data={
            "source": "system",
            "sequence": "0",
            "started_at_ms": "0",
            "duration_ms": "5000",
            "sha256_hex": sha256(payload).hexdigest(),
        },
        files={"audio": ("chunk.webm", payload, "audio/webm")},
    )

    assert response.status_code == 422


def test_checkpoint_finalize_and_retry_delegate_to_processing_coordinator(
    settings: Settings, auth: dict[str, str]
) -> None:
    class FakeCoordinator:
        def __init__(self) -> None:
            self.finalized: list[str] = []

        def checkpoint(self, session_id: str) -> MeetingMinutes:
            return MeetingMinutes(
                meeting_id=session_id,
                title="Checkpoint",
                summary="Tóm tắt tạm thời.",
            )

        def submit_finalize(self, session_id: str):
            self.finalized.append(session_id)
            return {"session_id": session_id, "status": "processing"}

        def retry(self, session_id: str):
            return self.submit_finalize(session_id)

        def status(self, session_id: str):
            return {"session_id": session_id, "status": "processing"}

    coordinator = FakeCoordinator()
    client = TestClient(create_app(settings, coordinator=coordinator))
    session_id = client.post("/v1/sessions", json={"title": "Process me"}, headers=auth).json()[
        "id"
    ]

    checkpoint = client.post(f"/v1/sessions/{session_id}/checkpoint", headers=auth)
    finalize = client.post(f"/v1/sessions/{session_id}/finalize", headers=auth)
    state = client.get(f"/v1/sessions/{session_id}", headers=auth)
    retry = client.post(f"/v1/sessions/{session_id}/retry", headers=auth)

    assert checkpoint.status_code == 200
    assert checkpoint.json()["summary"] == "Tóm tắt tạm thời."
    assert finalize.status_code == 202
    assert state.json()["status"] == "processing"
    assert retry.status_code == 202
    assert coordinator.finalized == [session_id, session_id]


def test_processing_resource_controls_delegate_to_coordinator(
    settings: Settings, auth: dict[str, str]
) -> None:
    class FakeCoordinator:
        def pause(self, session_id: str):
            return {"session_id": session_id, "status": "paused"}

        def resume(self, session_id: str):
            return {"session_id": session_id, "status": "processing"}

        def fast(self, session_id: str):
            return {"session_id": session_id, "status": "processing", "mode": "fast"}

    client = TestClient(create_app(settings, coordinator=FakeCoordinator()))

    paused = client.post("/v1/sessions/example/pause", headers=auth)
    resumed = client.post("/v1/sessions/example/resume", headers=auth)
    fast = client.post("/v1/sessions/example/fast", headers=auth)

    assert paused.json()["status"] == "paused"
    assert resumed.json()["status"] == "processing"
    assert fast.json()["mode"] == "fast"


def test_minutes_can_be_read_and_edited_without_changing_meeting_identity(
    settings: Settings, auth: dict[str, str]
) -> None:
    from meet_assistant.storage import MeetingRepository

    repository = MeetingRepository(settings)
    meeting_dir = settings.meetings_dir / "2026-08-03_daily"
    meeting_dir.mkdir(parents=True)
    (meeting_dir / "recording.webm").write_bytes(b"audio")
    original = MeetingMinutes(meeting_id="fixed-id", title="Daily", summary="Bản đầu")
    (meeting_dir / "minutes.json").write_text(original.model_dump_json(indent=2), "utf-8")
    client = TestClient(create_app(settings))

    loaded = client.get("/v1/sessions/fixed-id/minutes", headers=auth)
    edited = client.patch(
        "/v1/sessions/fixed-id/minutes",
        headers=auth,
        json={"meeting_id": "attacker-id", "summary": "Đã sửa"},
    )

    assert loaded.status_code == 200
    assert loaded.json()["summary"] == "Bản đầu"
    assert edited.status_code == 200
    assert edited.json()["meeting_id"] == "fixed-id"
    assert repository.load_minutes("fixed-id").summary == "Đã sửa"


def test_completed_meetings_are_listed_separately_from_recoverable_sessions(
    settings: Settings, auth: dict[str, str]
) -> None:
    meeting_dir = settings.meetings_dir / "2026-08-06_meet"
    meeting_dir.mkdir(parents=True)
    (meeting_dir / "recording.webm").write_bytes(b"audio")
    (meeting_dir / "minutes.json").write_text(
        MeetingMinutes(meeting_id="completed-id", title="Completed meeting", summary="Done").model_dump_json(),
        encoding="utf-8",
    )

    client = TestClient(create_app(settings))
    response = client.get("/v1/meetings", headers=auth)

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "completed-id",
            "title": "Completed meeting",
            "output_dir": str(meeting_dir),
        }
    ]


def test_chunk_upload_stops_when_disk_reaches_emergency_threshold(
    settings: Settings, auth: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(create_app(settings))
    session_id = client.post("/v1/sessions", json={"title": "Disk guard"}, headers=auth).json()[
        "id"
    ]
    monkeypatch.setattr(settings, "free_space_gb", lambda: 0.5)
    payload = b"audio"

    response = client.post(
        f"/v1/sessions/{session_id}/chunks",
        headers=auth,
        data={
            "source": "remote",
            "sequence": "0",
            "started_at_ms": "0",
            "duration_ms": "5000",
            "sha256_hex": sha256(payload).hexdigest(),
        },
        files={"audio": ("chunk.webm", payload, "audio/webm")},
    )

    assert response.status_code == 507
    assert response.json()["detail"]["code"] == "disk_stop"


def test_failed_or_abandoned_session_can_be_deleted(
    settings: Settings, auth: dict[str, str]
) -> None:
    from meet_assistant.storage import MeetingRepository

    client = TestClient(create_app(settings))
    session_id = client.post(
        "/v1/sessions", json={"title": "Delete recovery"}, headers=auth
    ).json()["id"]
    repository = MeetingRepository(settings)

    response = client.delete(f"/v1/sessions/{session_id}", headers=auth)

    assert response.status_code == 204
    assert not repository.work_path(session_id).exists()
