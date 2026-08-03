from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_file_logging(
    logs_dir: Path, *, max_bytes: int = 2 * 1024 * 1024, backups: int = 3
) -> logging.Logger:
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("meet_assistant")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for existing in logger.handlers:
        existing.close()
    logger.handlers.clear()
    handler = RotatingFileHandler(
        logs_dir / "helper.log",
        maxBytes=max_bytes,
        backupCount=backups,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger
