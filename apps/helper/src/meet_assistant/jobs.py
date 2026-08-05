from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from threading import Event, Lock, Thread
from typing import Any

from .domain import MeetingMinutes
from .pipeline import FinalizationPipeline
from .resources import PauseGate, ResourceController
from .storage import MeetingRepository, SessionNotFoundError
from .summarization import Summarizer, enforce_evidence_policy
from .transcription import merge_transcripts


class ProcessingCoordinator:
    def __init__(
        self,
        repository: MeetingRepository,
        pipeline: FinalizationPipeline,
        summarizer: Summarizer,
        pause_gate: PauseGate | None = None,
        resource_controller: ResourceController | None = None,
    ) -> None:
        self.repository = repository
        self.pipeline = pipeline
        self.summarizer = summarizer
        self.pause_gate = pause_gate or PauseGate()
        self.resource_controller = resource_controller or ResourceController()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="meet-finalize")
        self._jobs: dict[str, dict[str, Any]] = {}
        self._futures: dict[str, Future] = {}
        self._lock = Lock()

    def checkpoint(self, session_id: str) -> MeetingMinutes:
        manifest = self.repository.load_manifest(session_id)
        captions = self.repository.load_captions(session_id)
        transcript = merge_transcripts(captions, [])
        minutes = self.summarizer.summarize(session_id, manifest.title, transcript)
        return enforce_evidence_policy(
            minutes.model_copy(update={"transcript": transcript, "language": manifest.language})
        )

    def regenerate(self, session_id: str) -> MeetingMinutes:
        current = self.repository.load_minutes(session_id)
        generated = self.summarizer.summarize(session_id, current.title, current.transcript)
        preserved = {
            "meeting_id": session_id,
            "title": current.title,
            "started_at": current.started_at,
            "ended_at": current.ended_at,
            "duration_ms": current.duration_ms,
            "language": current.language,
            "participants": current.participants,
            "transcript": current.transcript,
        }
        regenerated = enforce_evidence_policy(generated.model_copy(update=preserved))
        return self.repository.update_minutes(session_id, regenerated.model_dump(mode="json"))

    def _finish(self, session_id: str, future: Future) -> None:
        try:
            result = future.result()
            state = {
                "session_id": session_id,
                "status": "completed",
                "output_dir": str(result.output_dir),
                "error": None,
            }
        except Exception as error:  # noqa: BLE001 - job boundary must persist every failure
            state = {
                "session_id": session_id,
                "status": "failed",
                "output_dir": None,
                "error": str(error),
            }
        with self._lock:
            self._jobs[session_id] = state

    def _monitor_resources(self, session_id: str, stop: Event) -> None:
        auto_paused = False
        is_over_limit = getattr(self.resource_controller, "is_over_memory_limit", lambda: False)
        while not stop.wait(1.0):
            over_limit = bool(is_over_limit())
            with self._lock:
                state = self._jobs.get(session_id)
                if not state:
                    continue
                if over_limit and state["status"] == "processing":
                    self.pause_gate.pause()
                    self._jobs[session_id] = {
                        **state,
                        "status": "paused",
                        "pause_reason": "memory_limit",
                    }
                    auto_paused = True
                elif (
                    auto_paused
                    and not over_limit
                    and state["status"] == "paused"
                    and state.get("pause_reason") == "memory_limit"
                ):
                    self.pause_gate.resume()
                    self._jobs[session_id] = {
                        **state,
                        "status": "processing",
                        "pause_reason": None,
                    }
                    auto_paused = False

    def submit_finalize(self, session_id: str) -> dict[str, Any]:
        manifest = self.repository.load_manifest(session_id)
        with self._lock:
            existing = self._jobs.get(session_id)
            if existing and existing["status"] == "processing":
                return existing
            state = {
                "session_id": session_id,
                "status": "processing",
                "stage": manifest.processing_stage or "audio",
                "progress": manifest.processing_progress,
                "error": None,
            }
            self._jobs[session_id] = state

        def run_pipeline():
            self.resource_controller.set_mode("postprocess")
            monitor_stop = Event()
            monitor = Thread(
                target=self._monitor_resources,
                args=(session_id, monitor_stop),
                name=f"meet-resources-{session_id[:8]}",
                daemon=True,
            )
            monitor.start()
            try:
                return self.pipeline.finalize(session_id)
            finally:
                monitor_stop.set()
                monitor.join(timeout=2)
                self.resource_controller.set_mode("meeting")

        future = self._executor.submit(run_pipeline)
        with self._lock:
            self._futures[session_id] = future
        # A very short pipeline can finish before add_done_callback is called.
        # Register outside the lock so an immediate callback cannot deadlock in _finish.
        future.add_done_callback(lambda value: self._finish(session_id, value))
        return state

    def pause(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._jobs.get(session_id)
            if not state or state["status"] != "processing":
                raise ValueError("Only a processing session can be paused")
            self.pause_gate.pause()
            state = {**state, "status": "paused"}
            self._jobs[session_id] = state
            return dict(state)

    def resume(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._jobs.get(session_id)
            if not state or state["status"] != "paused":
                raise ValueError("Only a paused session can be resumed")
            self.pause_gate.resume()
            state = {**state, "status": "processing"}
            self._jobs[session_id] = state
            return dict(state)

    def fast(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._jobs.get(session_id)
            if not state or state["status"] not in {"processing", "paused"}:
                raise ValueError("Only an active processing session can use fast mode")
            self.pause_gate.resume()
            self.resource_controller.set_mode("fast")
            state = {**state, "status": "processing", "mode": "fast"}
            self._jobs[session_id] = state
            return dict(state)

    def retry(self, session_id: str) -> dict[str, Any]:
        manifest = self.repository.load_manifest(session_id)
        if manifest.status not in {"failed", "processing", "recording"}:
            raise ValueError("Session is not recoverable")
        return self.submit_finalize(session_id)

    def status(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            if session_id in self._jobs:
                state = dict(self._jobs[session_id])
                manifest = self.repository.load_manifest(session_id)
                state.update({"stage": manifest.processing_stage, "progress": manifest.processing_progress})
                return state
        try:
            minutes = self.repository.load_minutes(session_id)
            return {
                "session_id": session_id,
                "status": "completed",
                "title": minutes.title,
                "error": None,
                "stage": "completed",
                "progress": 100,
            }
        except SessionNotFoundError:
            manifest = self.repository.load_manifest(session_id)
            return {
                "session_id": session_id,
                "status": manifest.status,
                "title": manifest.title,
                "error": manifest.error,
                "stage": manifest.processing_stage,
                "progress": manifest.processing_progress,
            }
