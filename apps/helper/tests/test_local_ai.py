from pathlib import Path

import pytest

from meet_assistant.config import Settings, configure_process_environment
from meet_assistant.domain import TranscriptSegment
from meet_assistant.local_ai import (
    LocalModelPaths,
    ModelUnavailableError,
    chunk_transcript,
    parse_model_minutes,
)


def test_model_paths_stay_under_runtime_models(tmp_path: Path) -> None:
    project = tmp_path / "project"
    settings = Settings(project_root=project, runtime_root=project / "runtime")
    configure_process_environment(settings)

    paths = LocalModelPaths.from_settings(settings)

    assert paths.whisper_dir.is_relative_to(settings.models_dir)
    assert paths.qwen_model.is_relative_to(settings.models_dir)
    assert paths.llama_cli.is_relative_to(settings.models_dir)


def test_missing_model_diagnostic_names_install_script(tmp_path: Path) -> None:
    project = tmp_path / "project"
    settings = Settings(project_root=project, runtime_root=project / "runtime")
    configure_process_environment(settings)

    with pytest.raises(ModelUnavailableError, match="install-models.ps1"):
        LocalModelPaths.from_settings(settings).require_summary_model()


def test_parse_model_minutes_ignores_wrapping_text_and_preserves_null_fields() -> None:
    transcript = [
        TranscriptSegment(
            start_ms=1000,
            end_ms=2000,
            speaker="Lan",
            text="Cần gửi tài liệu.",
            source="caption",
        )
    ]
    output = """Schema được echo: {"summary": string}\nKết quả:\n```json
{"summary":"Có một đầu việc.","topics":["Tài liệu"],"decisions":[],
"action_items":[{"task":"Gửi tài liệu","assignee":null,"deadline":null,
"status":"needs_confirmation","evidence":[{"timestamp_ms":1000,"speaker":"Lan",
"quote":"Cần gửi tài liệu."}]}],"open_questions":[]}
```"""

    minutes = parse_model_minutes("id-1", "Daily", transcript, output)

    assert minutes.summary == "Có một đầu việc."
    assert minutes.action_items[0].assignee is None
    assert minutes.action_items[0].deadline is None
    assert minutes.transcript == transcript


def test_long_transcript_is_split_on_segment_boundaries() -> None:
    transcript = [
        TranscriptSegment(
            start_ms=index * 1000,
            end_ms=index * 1000 + 900,
            speaker="Lan",
            text=f"Đoạn {index} " + ("x" * 20),
            source="caption",
        )
        for index in range(5)
    ]

    chunks = chunk_transcript(transcript, max_chars=70)

    assert len(chunks) > 1
    assert [item.start_ms for chunk in chunks for item in chunk] == [0, 1000, 2000, 3000, 4000]
    assert all(sum(len(item.text) for item in chunk) <= 70 for chunk in chunks)
