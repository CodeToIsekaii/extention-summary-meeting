from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import imageio_ffmpeg


class LocalAudioFinalizer:
    def __init__(self, ffmpeg_executable: str | None = None) -> None:
        self.ffmpeg_executable = ffmpeg_executable or imageio_ffmpeg.get_ffmpeg_exe()

    @staticmethod
    def _assemble(source_dir: Path, destination: Path) -> Path | None:
        chunks = sorted(source_dir.glob("*.webm"))
        if not chunks:
            return None
        with destination.open("wb") as target:
            for chunk in chunks:
                with chunk.open("rb") as source:
                    shutil.copyfileobj(source, target)
        return destination

    def finalize(self, session_path: Path, output_path: Path) -> None:
        remote = self._assemble(
            session_path / "chunks" / "remote", session_path / "assembled-remote.webm"
        )
        microphone = self._assemble(
            session_path / "chunks" / "me", session_path / "assembled-me.webm"
        )
        inputs = [item for item in (remote, microphone) if item is not None]
        if not inputs:
            raise RuntimeError("No audio chunks are available for finalization")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        command = [self.ffmpeg_executable, "-hide_banner", "-loglevel", "error"]
        for item in inputs:
            command.extend(["-i", str(item)])
        if len(inputs) == 2:
            command.extend(
                [
                    "-filter_complex",
                    "[0:a][1:a]amix=inputs=2:duration=longest:dropout_transition=0[a]",
                    "-map",
                    "[a]",
                ]
            )
        else:
            command.extend(["-map", "0:a"])
        command.extend(["-c:a", "libopus", "-b:a", "96k", "-y", str(output_path)])
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {result.stderr.strip()}")
        verification = subprocess.run(
            [
                self.ffmpeg_executable,
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(output_path),
                "-f",
                "null",
                os.devnull,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if verification.returncode != 0:
            raise RuntimeError(
                f"Final recording could not be decoded: {verification.stderr.strip()}"
            )
