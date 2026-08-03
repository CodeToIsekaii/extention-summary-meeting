from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DiskStatus:
    free_gb: float
    can_start: bool
    warning: bool
    must_stop: bool


@dataclass
class Settings:
    project_root: Path
    runtime_root: Path
    helper_host: str = "127.0.0.1"
    helper_port: int = 8765
    auth_token: str = "development-token-change-me"
    minimum_start_free_gb: float = 5.0
    warning_free_gb: float = 3.0
    stop_free_gb: float = 1.0
    buffer_seconds: int = 30
    meeting_cpu_percent: int = 25
    postprocess_cpu_percent: int = 50
    max_memory_gb: float = 4.0
    whisper_model: str = "faster-whisper-medium"
    summary_model_file: str = "Qwen3-4B-Q5_K_M.gguf"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"

    def __post_init__(self) -> None:
        self.project_root = Path(self.project_root).resolve()
        self.runtime_root = Path(self.runtime_root).resolve()
        if not self.runtime_root.is_relative_to(self.project_root):
            raise ValueError("runtime_root must be inside project_root")
        if self.helper_host != "127.0.0.1":
            raise ValueError("helper_host must be 127.0.0.1")
        if not self.stop_free_gb < self.warning_free_gb < self.minimum_start_free_gb:
            raise ValueError("disk thresholds must satisfy stop < warning < start")
        if not 1 <= self.meeting_cpu_percent <= self.postprocess_cpu_percent <= 100:
            raise ValueError("CPU limits must satisfy 1 <= meeting <= postprocess <= 100")
        if self.max_memory_gb <= 0:
            raise ValueError("max_memory_gb must be positive")

    @property
    def models_dir(self) -> Path:
        return self.runtime_root / "models"

    @property
    def work_dir(self) -> Path:
        return self.runtime_root / "work"

    @property
    def meetings_dir(self) -> Path:
        return self.runtime_root / "meetings"

    @property
    def temp_dir(self) -> Path:
        return self.runtime_root / "tmp"

    @property
    def logs_dir(self) -> Path:
        return self.runtime_root / "logs"

    def free_space_gb(self) -> float:
        anchor = self.runtime_root if self.runtime_root.exists() else self.project_root
        return shutil.disk_usage(anchor).free / (1024**3)

    def disk_status(self) -> DiskStatus:
        free_gb = self.free_space_gb()
        return DiskStatus(
            free_gb=round(free_gb, 2),
            can_start=free_gb >= self.minimum_start_free_gb,
            warning=self.stop_free_gb <= free_gb < self.warning_free_gb,
            must_stop=free_gb < self.stop_free_gb,
        )

    @classmethod
    def for_project(cls, project_root: Path | None = None) -> Settings:
        root = (project_root or Path(__file__).resolve().parents[4]).resolve()
        values: dict = {}
        config_path = root / "config" / "settings.json"
        if config_path.is_file():
            values = json.loads(config_path.read_text(encoding="utf-8"))
        allowed = {
            "runtime_root",
            "helper_host",
            "helper_port",
            "auth_token",
            "minimum_start_free_gb",
            "warning_free_gb",
            "stop_free_gb",
            "buffer_seconds",
            "meeting_cpu_percent",
            "postprocess_cpu_percent",
            "max_memory_gb",
            "whisper_model",
            "summary_model_file",
            "whisper_device",
            "whisper_compute_type",
        }
        configured = {key: value for key, value in values.items() if key in allowed}
        configured["runtime_root"] = Path(configured.get("runtime_root", root / "runtime"))
        configured["auth_token"] = os.environ.get(
            "MEET_ASSISTANT_TOKEN",
            configured.get("auth_token", "development-token-change-me"),
        )
        return cls(project_root=root, **configured)


def configure_process_environment(settings: Settings) -> None:
    for directory in (
        settings.runtime_root,
        settings.models_dir,
        settings.work_dir,
        settings.meetings_dir,
        settings.temp_dir,
        settings.logs_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    cache_root = settings.runtime_root / "cache"
    hf_home = cache_root / "huggingface"
    hf_hub = hf_home / "hub"
    for directory in (cache_root, hf_home, hf_hub):
        directory.mkdir(parents=True, exist_ok=True)

    os.environ.update(
        {
            "HF_HOME": str(hf_home),
            "HUGGINGFACE_HUB_CACHE": str(hf_hub),
            "XDG_CACHE_HOME": str(cache_root),
            "TMP": str(settings.temp_dir),
            "TEMP": str(settings.temp_dir),
        }
    )
