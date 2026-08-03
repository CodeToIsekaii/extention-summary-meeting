from __future__ import annotations

import uvicorn

from .api import create_app
from .config import Settings
from .logging_config import configure_file_logging
from .resources import ResourceController


def run() -> None:
    settings = Settings.for_project()
    logger = configure_file_logging(settings.logs_dir)
    resource_controller = ResourceController(
        meeting_percent=settings.meeting_cpu_percent,
        postprocess_percent=settings.postprocess_cpu_percent,
        max_memory_gb=settings.max_memory_gb,
    )
    resource_controller.set_mode("meeting")
    logger.info("Starting helper on %s:%s", settings.helper_host, settings.helper_port)
    uvicorn.run(
        create_app(settings, resource_controller=resource_controller),
        host=settings.helper_host,
        port=settings.helper_port,
        log_level="info",
    )


if __name__ == "__main__":
    run()
