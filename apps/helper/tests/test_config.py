from pathlib import Path

import pytest

from meet_assistant.config import Settings, configure_process_environment


def test_settings_reject_runtime_outside_project(tmp_path: Path) -> None:
    project = tmp_path / "project"
    outside = tmp_path / "outside"

    with pytest.raises(ValueError, match="runtime_root must be inside project_root"):
        Settings(project_root=project, runtime_root=outside)


def test_configure_environment_routes_model_and_temp_caches_to_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    runtime = project / "runtime"
    settings = Settings(project_root=project, runtime_root=runtime)
    for key in ("HF_HOME", "HUGGINGFACE_HUB_CACHE", "TMP", "TEMP"):
        monkeypatch.delenv(key, raising=False)

    configure_process_environment(settings)

    assert Path(settings.models_dir).is_dir()
    assert Path(settings.work_dir).is_dir()
    assert Path(settings.meetings_dir).is_dir()
    assert Path(settings.temp_dir).is_dir()
    assert Path(settings.logs_dir).is_dir()
    assert Path(__import__("os").environ["HF_HOME"]).is_relative_to(runtime)
    assert Path(__import__("os").environ["TMP"]) == settings.temp_dir


def test_disk_status_enforces_start_warning_and_stop_thresholds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    settings = Settings(project_root=project, runtime_root=project / "runtime")
    monkeypatch.setattr(settings, "free_space_gb", lambda: 4.5)

    status = settings.disk_status()

    assert status.can_start is False
    assert status.warning is False
    assert status.must_stop is False

