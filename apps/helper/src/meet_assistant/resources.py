from __future__ import annotations

import os
from threading import Event
from typing import Literal

import psutil


class PauseGate:
    def __init__(self) -> None:
        self._resume = Event()
        self._resume.set()

    @property
    def is_paused(self) -> bool:
        return not self._resume.is_set()

    def pause(self) -> None:
        self._resume.clear()

    def resume(self) -> None:
        self._resume.set()

    def wait(self) -> None:
        self._resume.wait()


class ResourceController:
    def __init__(
        self,
        *,
        process=None,
        logical_cpu_count: int | None = None,
        meeting_percent: int = 25,
        postprocess_percent: int = 50,
        max_memory_gb: float = 5.0,
    ) -> None:
        self.process = process or psutil.Process()
        self.logical_cpu_count = logical_cpu_count or psutil.cpu_count(logical=True) or 1
        self.meeting_percent = meeting_percent
        self.postprocess_percent = postprocess_percent
        self.memory_limit_bytes = round(max_memory_gb * 1024**3)
        try:
            self.original_affinity = self.process.cpu_affinity()
        except (AttributeError, psutil.Error):
            self.original_affinity = list(range(self.logical_cpu_count))

    def set_mode(self, mode: Literal["meeting", "postprocess", "fast"]) -> None:
        percentages = {
            "meeting": self.meeting_percent,
            "postprocess": self.postprocess_percent,
            "fast": 100,
        }
        percent = percentages[mode]
        count = max(1, round(self.logical_cpu_count * percent / 100))
        affinity = self.original_affinity[:count]
        try:
            self.process.cpu_affinity(affinity)
        except (AttributeError, psutil.Error):
            pass
        try:
            priority = getattr(psutil, "BELOW_NORMAL_PRIORITY_CLASS", 10)
            self.process.nice(priority)
        except (AttributeError, psutil.Error):
            pass
        os.environ["OMP_NUM_THREADS"] = str(count)
        os.environ["CT2_THREADS"] = str(count)

    def memory_usage_bytes(self) -> int:
        processes = [self.process]
        try:
            processes.extend(self.process.children(recursive=True))
        except (AttributeError, psutil.Error):
            pass
        total = 0
        for process in processes:
            try:
                total += process.memory_info().rss
            except (AttributeError, psutil.Error):
                continue
        return total

    def is_over_memory_limit(self) -> bool:
        return self.memory_usage_bytes() > self.memory_limit_bytes

    def restore(self) -> None:
        try:
            self.process.cpu_affinity(self.original_affinity)
        except (AttributeError, psutil.Error):
            pass
