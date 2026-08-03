from meet_assistant.resources import PauseGate, ResourceController


class MemoryInfo:
    def __init__(self, rss: int) -> None:
        self.rss = rss


class FakeProcess:
    def __init__(self) -> None:
        self.affinity = list(range(16))
        self.priorities: list[int] = []

    def cpu_affinity(self, value=None):
        if value is None:
            return list(self.affinity)
        self.affinity = list(value)

    def nice(self, value: int) -> None:
        self.priorities.append(value)

    def memory_info(self):
        return MemoryInfo(3 * 1024**3)

    def children(self, recursive: bool = True):
        child = FakeProcess()
        child.memory_info = lambda: MemoryInfo(2 * 1024**3)
        child.children = lambda recursive=True: []
        return [child]


def test_resource_modes_limit_affinity_to_25_and_50_percent() -> None:
    process = FakeProcess()
    controller = ResourceController(process=process, logical_cpu_count=16)

    controller.set_mode("meeting")
    assert process.affinity == [0, 1, 2, 3]

    controller.set_mode("postprocess")
    assert process.affinity == list(range(8))

    controller.set_mode("fast")
    assert process.affinity == list(range(16))


def test_pause_gate_reports_and_resumes_cooperative_pause() -> None:
    gate = PauseGate()

    gate.pause()
    assert gate.is_paused is True

    gate.resume()
    assert gate.is_paused is False


def test_memory_limit_includes_local_model_child_processes() -> None:
    controller = ResourceController(process=FakeProcess(), max_memory_gb=4)

    assert controller.is_over_memory_limit() is True
