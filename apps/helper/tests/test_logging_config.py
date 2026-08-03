from pathlib import Path

from meet_assistant.logging_config import configure_file_logging


def test_logs_are_written_to_bounded_runtime_file(tmp_path: Path) -> None:
    logger = configure_file_logging(tmp_path, max_bytes=1024, backups=2)

    logger.info("helper started")
    for handler in logger.handlers:
        handler.flush()

    assert (tmp_path / "helper.log").read_text("utf-8").find("helper started") >= 0
    handler = logger.handlers[0]
    assert handler.maxBytes == 1024
    assert handler.backupCount == 2
