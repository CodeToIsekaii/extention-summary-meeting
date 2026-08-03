from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

import imageio_ffmpeg
from fastapi.testclient import TestClient
from meet_assistant.api import create_app
from meet_assistant.config import Settings


def create_track(path: Path, frequency: int) -> bytes:
    subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={frequency}:duration=1",
            "-c:a",
            "libopus",
            "-y",
            str(path),
        ],
        check=True,
    )
    return path.read_bytes()


def main() -> None:
    settings = Settings.for_project()
    scratch = settings.temp_dir / "e2e-smoke"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    headers = {"Authorization": f"Bearer {settings.auth_token}"}
    client = TestClient(create_app(settings))
    session_id = ""
    output_dir: Path | None = None
    try:
        created = client.post(
            "/v1/sessions",
            headers=headers,
            json={"title": "E2E Smoke", "language": "vi"},
        )
        created.raise_for_status()
        session_id = created.json()["id"]
        for source, frequency in (("remote", 440), ("me", 660)):
            payload = create_track(scratch / f"{source}.webm", frequency)
            response = client.post(
                f"/v1/sessions/{session_id}/chunks",
                headers=headers,
                data={
                    "source": source,
                    "sequence": "0",
                    "started_at_ms": "0",
                    "duration_ms": "1000",
                    "sha256_hex": hashlib.sha256(payload).hexdigest(),
                },
                files={"audio": (f"{source}.webm", payload, "audio/webm")},
            )
            response.raise_for_status()
        caption = client.post(
            f"/v1/sessions/{session_id}/captions",
            headers=headers,
            json=[
                {
                    "start_ms": 100,
                    "end_ms": 900,
                    "speaker": "Lan",
                    "text": "Minh sẽ gửi báo cáo trước thứ Sáu.",
                }
            ],
        )
        caption.raise_for_status()
        finalized = client.post(f"/v1/sessions/{session_id}/finalize", headers=headers)
        finalized.raise_for_status()
        deadline = time.monotonic() + 180
        state = finalized.json()
        while (
            state["status"] in {"processing", "paused"} and time.monotonic() < deadline
        ):
            time.sleep(1)
            state = client.get(f"/v1/sessions/{session_id}", headers=headers).json()
        if state["status"] != "completed":
            raise RuntimeError(f"E2E finalization failed: {state}")
        output_dir = Path(state["output_dir"])
        files = sorted(path.name for path in output_dir.iterdir())
        if files != ["minutes.json", "recording.webm"]:
            raise RuntimeError(f"Unexpected final files: {files}")
        minutes = json.loads((output_dir / "minutes.json").read_text("utf-8"))
        if not minutes["action_items"] or not minutes["action_items"][0]["evidence"]:
            raise RuntimeError("E2E minutes did not preserve task evidence")
        if settings.work_dir.joinpath(session_id).exists():
            raise RuntimeError(
                "Successful E2E session was not removed from runtime/work"
            )
        print(
            json.dumps(
                {
                    "status": "ok",
                    "session_id": session_id,
                    "files": files,
                    "tasks": len(minutes["action_items"]),
                },
                ensure_ascii=False,
            )
        )
    finally:
        if scratch.exists():
            shutil.rmtree(scratch)
        if (
            output_dir is not None
            and output_dir.exists()
            and output_dir.resolve().is_relative_to(settings.meetings_dir.resolve())
            and output_dir.name.endswith("e2e-smoke")
        ):
            shutil.rmtree(output_dir)


if __name__ == "__main__":
    main()
