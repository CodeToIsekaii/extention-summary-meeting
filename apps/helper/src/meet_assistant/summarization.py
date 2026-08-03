from __future__ import annotations

from typing import Protocol

from .domain import ActionItem, MeetingMinutes, TranscriptSegment


class Summarizer(Protocol):
    def summarize(
        self, meeting_id: str, title: str, transcript: list[TranscriptSegment]
    ) -> MeetingMinutes: ...


def _evidence_matches_transcript(item: ActionItem, transcript: list[TranscriptSegment]) -> bool:
    for evidence in item.evidence:
        normalized_quote = evidence.quote.strip().casefold()
        for segment in transcript:
            timestamp_matches = segment.start_ms <= evidence.timestamp_ms <= segment.end_ms
            text_matches = (
                normalized_quote in segment.text.casefold()
                or segment.text.casefold() in normalized_quote
            )
            speaker_matches = not evidence.speaker or evidence.speaker == segment.speaker
            if timestamp_matches and text_matches and speaker_matches:
                return True
    return False


def enforce_evidence_policy(minutes: MeetingMinutes) -> MeetingMinutes:
    validated_items: list[ActionItem] = []
    for item in minutes.action_items:
        if not item.evidence:
            continue
        if minutes.transcript and not _evidence_matches_transcript(item, minutes.transcript):
            continue
        status = item.status
        if item.assignee is None or item.deadline is None:
            status = "needs_confirmation"
        validated_items.append(item.model_copy(update={"status": status}))
    return minutes.model_copy(update={"action_items": validated_items})
