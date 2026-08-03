from meet_assistant.domain import CaptionSegment, TranscriptSegment
from meet_assistant.transcription import merge_transcripts


def test_stt_corrects_words_but_overlapping_caption_supplies_speaker() -> None:
    captions = [CaptionSegment(start_ms=1000, end_ms=4000, speaker="Lan", text="Chốt thứ 6 nhé")]
    stt = [
        TranscriptSegment(
            start_ms=900,
            end_ms=4100,
            speaker=None,
            text="Chốt deadline vào thứ Sáu nhé.",
            source="stt_remote",
        )
    ]

    merged = merge_transcripts(captions, stt)

    assert len(merged) == 1
    assert merged[0].speaker == "Lan"
    assert merged[0].text == "Chốt deadline vào thứ Sáu nhé."
    assert merged[0].source == "hybrid"


def test_stt_without_caption_never_guesses_remote_speaker() -> None:
    stt = [
        TranscriptSegment(
            start_ms=5000,
            end_ms=6500,
            speaker=None,
            text="Tôi sẽ kiểm tra lại.",
            source="stt_remote",
        )
    ]

    merged = merge_transcripts([], stt)

    assert merged[0].speaker == "Chưa xác định"


def test_microphone_track_is_always_labelled_as_me() -> None:
    stt = [
        TranscriptSegment(
            start_ms=0,
            end_ms=1000,
            speaker=None,
            text="Tôi đồng ý.",
            source="stt_me",
        )
    ]

    merged = merge_transcripts([], stt)

    assert merged[0].speaker == "Tôi"


def test_captions_remain_available_when_stt_returns_nothing() -> None:
    captions = [CaptionSegment(start_ms=0, end_ms=1000, speaker="Minh", text="Bắt đầu nhé")]

    merged = merge_transcripts(captions, [])

    assert merged[0].text == "Bắt đầu nhé"
    assert merged[0].source == "caption"


def test_point_in_time_caption_assigns_confirmed_speaker_to_nearby_stt() -> None:
    captions = [CaptionSegment(start_ms=5000, end_ms=5000, speaker="Lan", text="Gửi báo cáo.")]
    stt = [
        TranscriptSegment(
            start_ms=4200,
            end_ms=5600,
            speaker=None,
            text="Gửi báo cáo trước thứ Sáu.",
            source="stt_remote",
        )
    ]

    merged = merge_transcripts(captions, stt)

    assert len(merged) == 1
    assert merged[0].speaker == "Lan"
    assert merged[0].source == "hybrid"
