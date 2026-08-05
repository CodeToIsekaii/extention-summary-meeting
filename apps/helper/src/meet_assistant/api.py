from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .auth import bearer_auth
from .config import Settings, configure_process_environment
from .domain import CaptionSegment, ChunkMetadata, SessionCreate
from .storage import ChunkConflictError, MeetingRepository, SessionNotFoundError


def create_app(
    settings: Settings | None = None,
    *,
    coordinator: Any | None = None,
    resource_controller: Any | None = None,
) -> FastAPI:
    settings = settings or Settings.for_project()
    configure_process_environment(settings)
    repository = MeetingRepository(settings)
    if coordinator is None:
        from .audio import LocalAudioFinalizer
        from .jobs import ProcessingCoordinator
        from .local_ai import FasterWhisperTranscriber, LlamaCppSummarizer
        from .pipeline import FinalizationPipeline
        from .resources import PauseGate, ResourceController

        summarizer = LlamaCppSummarizer(settings)
        pause_gate = PauseGate()
        pipeline = FinalizationPipeline(
            repository,
            audio_finalizer=LocalAudioFinalizer(),
            transcriber=FasterWhisperTranscriber(settings),
            summarizer=summarizer,
            pause_gate=pause_gate,
        )
        resource_controller = resource_controller or ResourceController(
            meeting_percent=settings.meeting_cpu_percent,
            postprocess_percent=settings.postprocess_cpu_percent,
            max_memory_gb=settings.max_memory_gb,
        )
        coordinator = ProcessingCoordinator(
            repository,
            pipeline,
            summarizer,
            pause_gate=pause_gate,
            resource_controller=resource_controller,
        )
    require_auth = bearer_auth(settings.auth_token)

    app = FastAPI(title="Meet Assistant Helper", version="0.1.0")
    app.state.settings = settings
    app.state.repository = repository
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^chrome-extension://[a-p]{32}$",
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.get("/v1/health")
    def health() -> dict:
        disk = settings.disk_status()
        return {"status": "ok", "version": app.version, "disk": asdict(disk)}

    @app.get("/v1/pairing")
    def pairing() -> dict[str, str]:
        return {"auth_token": settings.auth_token}

    @app.post(
        "/v1/sessions",
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(require_auth)],
    )
    def create_session(request: SessionCreate):
        disk = settings.disk_status()
        if not disk.can_start:
            raise HTTPException(
                status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
                detail={
                    "code": "insufficient_disk_space",
                    "message": "At least 5 GB free is required to start recording.",
                    "free_gb": disk.free_gb,
                },
            )
        return repository.create_session(request)

    @app.get("/v1/sessions", dependencies=[Depends(require_auth)])
    def list_sessions():
        return repository.list_recoverable()

    @app.post(
        "/v1/sessions/{session_id}/chunks",
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(require_auth)],
    )
    async def upload_chunk(
        session_id: str,
        source: Annotated[Literal["remote", "me"], Form()],
        sequence: Annotated[int, Form(ge=0)],
        started_at_ms: Annotated[int, Form(ge=0)],
        duration_ms: Annotated[int, Form(gt=0, le=60_000)],
        sha256_hex: Annotated[str, Form(pattern=r"^[0-9a-f]{64}$")],
        audio: Annotated[UploadFile, File()],
    ):
        disk = settings.disk_status()
        if disk.must_stop:
            raise HTTPException(
                status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
                detail={
                    "code": "disk_stop",
                    "message": "Recording stopped because drive D has less than 1 GB free.",
                    "free_gb": disk.free_gb,
                },
            )
        payload = await audio.read()
        try:
            metadata = ChunkMetadata(
                source=source,
                sequence=sequence,
                started_at_ms=started_at_ms,
                duration_ms=duration_ms,
                sha256=sha256_hex,
            )
            return repository.append_chunk(session_id, metadata, payload)
        except ChunkConflictError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "chunk_conflict", "message": str(error)},
            ) from error
        except SessionNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "session_not_found", "message": session_id},
            ) from error

    @app.post(
        "/v1/sessions/{session_id}/captions",
        dependencies=[Depends(require_auth)],
    )
    def upload_captions(session_id: str, captions: list[CaptionSegment]):
        try:
            return repository.append_captions(session_id, captions)
        except SessionNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "session_not_found", "message": session_id},
            ) from error

    @app.post(
        "/v1/sessions/{session_id}/checkpoint",
        dependencies=[Depends(require_auth)],
    )
    def checkpoint(session_id: str):
        try:
            return coordinator.checkpoint(session_id)
        except SessionNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail={"code": "session_not_found", "message": session_id},
            ) from error

    @app.post(
        "/v1/sessions/{session_id}/finalize",
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=[Depends(require_auth)],
    )
    def finalize(session_id: str):
        try:
            return coordinator.submit_finalize(session_id)
        except SessionNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail={"code": "session_not_found", "message": session_id},
            ) from error

    @app.post(
        "/v1/sessions/{session_id}/retry",
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=[Depends(require_auth)],
    )
    def retry(session_id: str):
        try:
            return coordinator.retry(session_id)
        except SessionNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail={"code": "session_not_found", "message": session_id},
            ) from error

    @app.post(
        "/v1/sessions/{session_id}/process",
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=[Depends(require_auth)],
    )
    def process(session_id: str):
        try:
            return coordinator.retry(session_id)
        except SessionNotFoundError as error:
            raise HTTPException(status_code=404, detail={"code": "session_not_found", "message": session_id}) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail={"code": "invalid_session_state", "message": str(error)}) from error

    @app.post("/v1/sessions/{session_id}/pause", dependencies=[Depends(require_auth)])
    def pause(session_id: str):
        try:
            return coordinator.pause(session_id)
        except ValueError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": "invalid_session_state", "message": str(error)},
            ) from error

    @app.post("/v1/sessions/{session_id}/resume", dependencies=[Depends(require_auth)])
    def resume(session_id: str):
        try:
            return coordinator.resume(session_id)
        except ValueError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": "invalid_session_state", "message": str(error)},
            ) from error

    @app.post("/v1/sessions/{session_id}/fast", dependencies=[Depends(require_auth)])
    def fast(session_id: str):
        try:
            return coordinator.fast(session_id)
        except ValueError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": "invalid_session_state", "message": str(error)},
            ) from error

    @app.get("/v1/sessions/{session_id}", dependencies=[Depends(require_auth)])
    def session_status(session_id: str):
        try:
            return coordinator.status(session_id)
        except SessionNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail={"code": "session_not_found", "message": session_id},
            ) from error

    @app.get("/v1/sessions/{session_id}/minutes", dependencies=[Depends(require_auth)])
    def get_minutes(session_id: str):
        try:
            return repository.load_minutes(session_id)
        except SessionNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail={"code": "session_not_found", "message": session_id},
            ) from error

    @app.get("/v1/meetings", dependencies=[Depends(require_auth)])
    def meetings():
        results: list[dict[str, Any]] = []
        for path in sorted(settings.meetings_dir.glob("*/minutes.json"), reverse=True):
            try:
                import json
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                continue
            results.append({"id": payload.get("meeting_id"), "title": payload.get("title", path.parent.name), "output_dir": str(path.parent)})
        return results

    @app.patch("/v1/sessions/{session_id}/minutes", dependencies=[Depends(require_auth)])
    def patch_minutes(session_id: str, patch: dict[str, Any]):
        try:
            return repository.update_minutes(session_id, patch)
        except SessionNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail={"code": "session_not_found", "message": session_id},
            ) from error

    @app.post(
        "/v1/sessions/{session_id}/minutes/regenerate",
        dependencies=[Depends(require_auth)],
    )
    def regenerate_minutes(session_id: str):
        try:
            return coordinator.regenerate(session_id)
        except SessionNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail={"code": "session_not_found", "message": session_id},
            ) from error

    @app.get("/v1/sessions/{session_id}/recording", dependencies=[Depends(require_auth)])
    def get_recording(session_id: str):
        try:
            return FileResponse(repository.recording_path(session_id), media_type="audio/webm")
        except SessionNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail={"code": "session_not_found", "message": session_id},
            ) from error

    @app.delete(
        "/v1/sessions/{session_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[Depends(require_auth)],
    )
    def delete_recoverable(session_id: str) -> Response:
        try:
            repository.delete_recoverable(session_id)
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        except SessionNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail={"code": "session_not_found", "message": session_id},
            ) from error

    return app
