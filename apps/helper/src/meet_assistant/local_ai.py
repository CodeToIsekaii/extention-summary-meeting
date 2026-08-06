from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import Settings
from .domain import MeetingMinutes, TranscriptSegment
from .summarization import enforce_evidence_policy

TECH_GLOSSARY = {
    "google sit": "Google Sheet", "google shit": "Google Sheet",
    "front end": "frontend", "back end": "backend", "type script": "TypeScript",
    "java script": "JavaScript", "fast api": "FastAPI", "git hub": "GitHub",
    "local host": "localhost", "end point": "endpoint", "web hook": "webhook",
    "data base": "database",
    "api": "API", "a pi": "API", "ui": "UI", "ux": "UX",
    "json": "JSON", "sql": "SQL", "html": "HTML", "css": "CSS",
    "node js": "Node.js", "next js": "Next.js", "vue js": "Vue.js",
    "post gre": "PostgreSQL", "my sequel": "MySQL", "redis": "Redis",
    "endpoint": "endpoint", "repository": "repository", "repo": "repo",
    "pull request": "pull request", "deploy": "deploy", "deployment": "deployment",
    "bug": "bug", "feature": "feature", "database": "database",
}
FILLER_PATTERNS = (
    r"^(ừ|uh|ờ|à|dạ|ok|okay|đây|rồi|vâng)(\s+(ừ|uh|ờ|à|dạ|ok|okay|đây|rồi|vâng)){1,}$",
    r"^(đây\s+){2,}đây$",
)


def clean_transcript(transcript: list[TranscriptSegment]) -> list[TranscriptSegment]:
    """Normalize common Vietnamese/technology STT errors without inventing content."""
    cleaned: list[TranscriptSegment] = []
    previous_key: tuple[int, str] | None = None
    for segment in transcript:
        text = re.sub(r"\s+", " ", segment.text).strip()
        original = text.casefold()
        for wrong, right in TECH_GLOSSARY.items():
            text = re.sub(rf"\b{re.escape(wrong)}\b", right, text, flags=re.IGNORECASE)
        if any(re.match(pattern, original) for pattern in FILLER_PATTERNS):
            continue
        key = (segment.start_ms // 2_000, text.casefold())
        if key == previous_key:
            continue
        previous_key = key
        cleaned.append(segment.model_copy(update={"text": text}))
    return cleaned


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
        return f"""Bạn là trợ lý biên bản cuộc họp công nghệ/lập trình. Trả về duy nhất JSON hợp lệ bằng tiếng Việt.
Chỉ dùng thông tin có trong transcript; không dùng kiến thức bên ngoài và không suy đoán.
Không biến câu hỏi, ý tưởng hoặc ví dụ thành quyết định/task đã giao. Mỗi action item phải
trích dẫn đúng một câu trong transcript cùng timestamp_ms và speaker. Nếu thiếu assignee
hoặc deadline, dùng null và status needs_confirmation. Nếu transcript đủ dài, summary phải
có ít nhất 5 câu, nêu bối cảnh, nội dung chính, quyết định và việc tiếp theo nếu có.
Schema: {{"summary": string, "topics": string[],
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
            "8192",
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

    @staticmethod
    def _synthesis_prompt(title: str, parts: list[MeetingMinutes]) -> str:
        summaries = []
        for index, part in enumerate(parts, 1):
            summaries.append(json.dumps({
                "part": index,
                "summary": part.summary,
                "topics": part.topics,
                "decisions": part.decisions,
                "action_items": [item.model_dump(mode="json") for item in part.action_items],
                "open_questions": part.open_questions,
            }, ensure_ascii=False))
        return f"""Bạn là biên tập viên biên bản họp công nghệ/lập trình.
Hãy tổng hợp các bản tóm tắt trung gian dưới đây thành một biên bản duy nhất bằng tiếng Việt.
Chỉ giữ thông tin có bằng chứng trong dữ liệu; không thêm kiến thức ngoài. Gộp ý trùng nhau,
không biến câu hỏi thành quyết định, không tự đoán người phụ trách/deadline. Summary phải
dài 5-10 câu nếu có đủ nội dung. Mỗi action item phải giữ evidence timestamp_ms/quote nếu
có; nếu không đủ bằng chứng thì loại bỏ task đó. Trả về duy nhất JSON theo schema:
{{"summary": string, "topics": string[], "decisions": string[],
"action_items": [{{"task": string, "assignee": string|null, "deadline": string|null,
"status": "confirmed"|"needs_confirmation", "evidence": [{{"timestamp_ms": number,
"speaker": string|null, "quote": string}}]}}], "open_questions": string[]}}

Tiêu đề: {title}
Bản tóm tắt trung gian:
{chr(10).join(summaries)}
/no_think
"""

    def _run_model_text(self, prompt: str) -> str:
        command = [
            str(self.paths.llama_cli), "-m", str(self.paths.qwen_model), "-t", str(self.threads),
            "-c", "8192", "-n", "1024", "--temp", "0.1", "--no-display-prompt",
            "--single-turn", "--no-conversation", "--reasoning", "off", "--reasoning-budget", "0",
            "-p", prompt,
        ]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        if result.returncode != 0:
            raise RuntimeError(f"llama.cpp failed: {result.stderr.strip()}")
        return result.stdout

    def summarize(
        self, meeting_id: str, title: str, transcript: list[TranscriptSegment]
    ) -> MeetingMinutes:
        self.paths.require_summary_model()
        transcript = clean_transcript(transcript)
        parts = [
            parse_model_minutes(meeting_id, title, chunk, self._run_model(title, chunk))
            for chunk in chunk_transcript(transcript)
        ]
        if len(parts) == 1:
            return parts[0].model_copy(update={"transcript": transcript})
        synthesis = self._run_model_text(self._synthesis_prompt(title, parts))
        combined = parse_model_minutes(meeting_id, title, transcript, synthesis)
        return enforce_evidence_policy(combined.model_copy(update={"transcript": transcript}))
