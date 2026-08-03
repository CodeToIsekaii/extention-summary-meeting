from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import Settings
from .domain import MeetingMinutes, TranscriptSegment
from .summarization import enforce_evidence_policy


class ModelUnavailableError(RuntimeError):
    pass


def chunk_transcript(
    transcript: list[TranscriptSegment], max_chars: int = 8_000
) -> list[list[TranscriptSegment]]:
    chunks: list[list[TranscriptSegment]] = []
    current: list[TranscriptSegment] = []
    current_chars = 0
    for segment in transcript:
        segment_chars = len(segment.text)
        if current and current_chars + segment_chars > max_chars:
            chunks.append(current)
            current = []
            current_chars = 0
        current.append(segment)
        current_chars += segment_chars
    if current:
        chunks.append(current)
    return chunks or [[]]


@dataclass(frozen=True)
class LocalModelPaths:
    whisper_dir: Path
    qwen_model: Path
    llama_cli: Path

    @classmethod
    def from_settings(cls, settings: Settings) -> LocalModelPaths:
        return cls(
            whisper_dir=settings.models_dir / settings.whisper_model,
            qwen_model=settings.models_dir / settings.summary_model_file,
            llama_cli=settings.models_dir / "llama.cpp" / "llama-cli.exe",
        )

    def require_transcription_model(self) -> None:
        if not self.whisper_dir.is_dir():
            raise ModelUnavailableError(
                f"Whisper model is missing at {self.whisper_dir}. Run scripts/install-models.ps1."
            )

    def require_summary_model(self) -> None:
        missing = [path for path in (self.qwen_model, self.llama_cli) if not path.is_file()]
        if missing:
            raise ModelUnavailableError(
                "Local summary model is missing. Run scripts/install-models.ps1. Missing: "
                + ", ".join(str(path) for path in missing)
            )


class FasterWhisperTranscriber:
    def __init__(self, settings: Settings, *, cpu_threads: int = 8) -> None:
        self.paths = LocalModelPaths.from_settings(settings)
        self.cpu_threads = cpu_threads
        self.device = settings.whisper_device
        self.compute_type = settings.whisper_compute_type

    def transcribe(self, session_path: Path) -> list[TranscriptSegment]:
        self.paths.require_transcription_model()
        try:
            from faster_whisper import WhisperModel
        except ImportError as error:
            raise ModelUnavailableError(
                "faster-whisper is not installed. Run scripts/setup.ps1."
            ) from error

        model = WhisperModel(
            str(self.paths.whisper_dir),
            device=self.device,
            compute_type=self.compute_type,
            cpu_threads=self.cpu_threads,
        )
        transcript: list[TranscriptSegment] = []
        for source, filename in (
            ("stt_remote", "assembled-remote.webm"),
            ("stt_me", "assembled-me.webm"),
        ):
            audio_path = session_path / filename
            if not audio_path.is_file():
                continue
            segments, _ = model.transcribe(
                str(audio_path), vad_filter=True, beam_size=5, word_timestamps=False
            )
            transcript.extend(
                TranscriptSegment(
                    start_ms=max(0, round(segment.start * 1000)),
                    end_ms=max(0, round(segment.end * 1000)),
                    speaker=None,
                    text=segment.text.strip(),
                    source=source,
                )
                for segment in segments
                if segment.text.strip()
            )
        return sorted(transcript, key=lambda item: (item.start_ms, item.end_ms))


def _extract_json(output: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", output, flags=re.DOTALL)
    if fenced:
        value = json.loads(fenced.group(1))
        if isinstance(value, dict):
            return value

    decoder = json.JSONDecoder()
    candidates: list[tuple[int, dict]] = []
    for start, character in enumerate(output):
        if character != "{":
            continue
        try:
            value, end = decoder.raw_decode(output[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            candidates.append((end, value))
    if not candidates:
        raise ValueError("Local model did not return a JSON object")

    expected_keys = {"summary", "topics", "decisions", "action_items", "open_questions"}
    matching = [item for item in candidates if expected_keys.issubset(item[1])]
    return max(matching or candidates, key=lambda item: item[0])[1]


def parse_model_minutes(
    meeting_id: str,
    title: str,
    transcript: list[TranscriptSegment],
    output: str,
) -> MeetingMinutes:
    value = _extract_json(output)
    value.update({"meeting_id": meeting_id, "title": title, "transcript": transcript})
    return enforce_evidence_policy(MeetingMinutes.model_validate(value))


class LlamaCppSummarizer:
    def __init__(self, settings: Settings, *, threads: int = 4) -> None:
        self.paths = LocalModelPaths.from_settings(settings)
        self.threads = threads

    @staticmethod
    def _prompt(title: str, transcript: list[TranscriptSegment]) -> str:
        transcript_lines = "\n".join(
            f"[{item.start_ms}ms] {item.speaker or 'Chưa xác định'}: {item.text}"
            for item in transcript
        )
        return f"""Bạn là trợ lý biên bản cuộc họp. Trả về duy nhất JSON hợp lệ bằng tiếng Việt.
Không suy đoán người phụ trách hoặc deadline. Mỗi action item phải trích dẫn đúng một câu
trong transcript cùng timestamp_ms và speaker. Nếu thiếu assignee/deadline, dùng null và
status needs_confirmation. Schema: {{"summary": string, "topics": string[],
"decisions": string[], "action_items": [{{"task": string, "assignee": string|null,
"deadline": string|null, "status": "confirmed"|"needs_confirmation",
"evidence": [{{"timestamp_ms": number, "speaker": string|null, "quote": string}}]}}],
"open_questions": string[]}}.

Tiêu đề: {title}
Transcript:
{transcript_lines}
/no_think
"""

    def _run_model(self, title: str, transcript: list[TranscriptSegment]) -> str:
        command = [
            str(self.paths.llama_cli),
            "-m",
            str(self.paths.qwen_model),
            "-t",
            str(self.threads),
            "-c",
            "4096",
            "-n",
            "768",
            "--temp",
            "0.1",
            "--no-display-prompt",
            "--single-turn",
            "--no-conversation",
            "--reasoning",
            "off",
            "--reasoning-budget",
            "0",
            "-p",
            self._prompt(title, transcript),
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"llama.cpp failed: {result.stderr.strip()}")
        return result.stdout

    @staticmethod
    def _deduplicate(values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))

    def summarize(
        self, meeting_id: str, title: str, transcript: list[TranscriptSegment]
    ) -> MeetingMinutes:
        self.paths.require_summary_model()
        parts = [
            parse_model_minutes(meeting_id, title, chunk, self._run_model(title, chunk))
            for chunk in chunk_transcript(transcript)
        ]
        if len(parts) == 1:
            return parts[0].model_copy(update={"transcript": transcript})
        combined = MeetingMinutes(
            meeting_id=meeting_id,
            title=title,
            summary="\n\n".join(part.summary for part in parts if part.summary),
            topics=self._deduplicate([item for part in parts for item in part.topics]),
            decisions=self._deduplicate([item for part in parts for item in part.decisions]),
            action_items=[item for part in parts for item in part.action_items],
            open_questions=self._deduplicate(
                [item for part in parts for item in part.open_questions]
            ),
            transcript=transcript,
        )
        return enforce_evidence_policy(combined)
