from __future__ import annotations

from typing import Protocol

from .domain import CaptionSegment, TranscriptSegment


class Transcriber(Protocol):
    def transcribe(self, session_path) -> list[TranscriptSegment]: ...


def _overlap_ms(caption: CaptionSegment, segment: TranscriptSegment) -> int:
    overlap = max(0, min(caption.end_ms, segment.end_ms) - max(caption.start_ms, segment.start_ms))
    if overlap > 0:
        return overlap
    if caption.start_ms == caption.end_ms:
        distance = min(
            abs(caption.start_ms - segment.start_ms),
            abs(caption.start_ms - segment.end_ms),
        )
        if segment.start_ms <= caption.start_ms <= segment.end_ms or distance <= 3_000:
            return 1
    return 0


def merge_transcripts(
    captions: list[CaptionSegment], stt_segments: list[TranscriptSegment]
) -> list[TranscriptSegment]:
    if not stt_segments:
        return [
            TranscriptSegment(
                start_ms=item.start_ms,
                end_ms=item.end_ms,
                speaker=item.speaker or "Chưa xác định",
                text=item.text,
                source="caption",
            )
            for item in captions
        ]

    merged: list[TranscriptSegment] = []
    used_caption_indexes: set[int] = set()
    for segment in stt_segments:
        overlaps = [
            (_overlap_ms(caption, segment), index, caption)
            for index, caption in enumerate(captions)
        ]
        overlap, index, caption = max(overlaps, default=(0, -1, None), key=lambda item: item[0])
        if segment.source == "stt_me":
            speaker = "Tôi"
        elif overlap > 0 and caption is not None:
            speaker = caption.speaker or "Chưa xác định"
            used_caption_indexes.add(index)
        else:
            speaker = "Chưa xác định"
        merged.append(
            segment.model_copy(
                update={"speaker": speaker, "source": "hybrid" if overlap > 0 else segment.source}
            )
        )

    for index, caption in enumerate(captions):
        if index not in used_caption_indexes and not any(
            _overlap_ms(caption, segment) > 0 for segment in stt_segments
        ):
            merged.append(
                TranscriptSegment(
                    start_ms=caption.start_ms,
                    end_ms=caption.end_ms,
                    speaker=caption.speaker or "Chưa xác định",
                    text=caption.text,
                    source="caption",
                )
            )
    return sorted(merged, key=lambda item: (item.start_ms, item.end_ms))
