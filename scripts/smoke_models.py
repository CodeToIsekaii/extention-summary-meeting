from __future__ import annotations

import json
import shutil
import subprocess

import imageio_ffmpeg
from meet_assistant.config import Settings, configure_process_environment
from meet_assistant.domain import TranscriptSegment
from meet_assistant.local_ai import FasterWhisperTranscriber, LlamaCppSummarizer


def main() -> None:
    settings = Settings.for_project()
    configure_process_environment(settings)
    smoke_dir = settings.temp_dir / "model-smoke"
    if smoke_dir.exists():
        shutil.rmtree(smoke_dir)
    smoke_dir.mkdir(parents=True)
    try:
        audio_path = smoke_dir / "assembled-remote.webm"
        subprocess.run(
            [
                imageio_ffmpeg.get_ffmpeg_exe(),
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=1",
                "-c:a",
                "libopus",
                "-y",
                str(audio_path),
            ],
            check=True,
        )
        whisper_segments = FasterWhisperTranscriber(settings, cpu_threads=2).transcribe(
            smoke_dir
        )
        transcript = [
            TranscriptSegment(
                start_ms=1000,
                end_ms=3000,
                speaker="Lan",
                text="Minh sẽ gửi báo cáo trước thứ Sáu.",
                source="caption",
            )
        ]
        minutes = LlamaCppSummarizer(settings, threads=4).summarize(
            "smoke-id", "Kiểm tra local AI", transcript
        )
        print(
            json.dumps(
                {
                    "status": "ok",
                    "whisper_segments": len(whisper_segments),
                    "qwen_tasks": len(minutes.action_items),
                    "qwen_evidence": sum(
                        len(item.evidence) for item in minutes.action_items
                    ),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    finally:
        if smoke_dir.exists():
            shutil.rmtree(smoke_dir)


if __name__ == "__main__":
    main()
