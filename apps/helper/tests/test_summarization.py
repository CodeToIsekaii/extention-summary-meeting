from meet_assistant.domain import (
    ActionItem,
    Evidence,
    MeetingMinutes,
    TranscriptSegment,
)
from meet_assistant.summarization import enforce_evidence_policy


def test_action_without_evidence_is_removed() -> None:
    minutes = MeetingMinutes(
        meeting_id="meeting-1",
        title="Planning",
        summary="Nhóm thống nhất kế hoạch.",
        action_items=[
            ActionItem(
                task="Lan gửi bản thiết kế",
                assignee="Lan",
                deadline="2026-08-07",
                status="confirmed",
                evidence=[],
            )
        ],
    )

    validated = enforce_evidence_policy(minutes)

    assert validated.action_items == []


def test_missing_owner_or_deadline_is_marked_needs_confirmation() -> None:
    minutes = MeetingMinutes(
        meeting_id="meeting-2",
        title="Daily",
        summary="Có một đầu việc mới.",
        action_items=[
            ActionItem(
                task="Kiểm tra log production",
                assignee=None,
                deadline=None,
                status="confirmed",
                evidence=[
                    Evidence(
                        timestamp_ms=3000,
                        speaker="Minh",
                        quote="Cần kiểm tra log production.",
                    )
                ],
            )
        ],
    )

    validated = enforce_evidence_policy(minutes)

    assert validated.action_items[0].status == "needs_confirmation"
    assert validated.action_items[0].assignee is None
    assert validated.action_items[0].deadline is None


def test_evidence_must_match_a_real_transcript_segment() -> None:
    minutes = MeetingMinutes(
        meeting_id="meeting-3",
        title="Review",
        summary="Review",
        transcript=[
            TranscriptSegment(
                start_ms=1000,
                end_ms=2500,
                speaker="Lan",
                text="Tôi sẽ gửi tài liệu.",
                source="caption",
            )
        ],
        action_items=[
            ActionItem(
                task="Gửi tài liệu",
                assignee="Lan",
                deadline=None,
                status="needs_confirmation",
                evidence=[
                    Evidence(timestamp_ms=9000, speaker="Lan", quote="Một câu không tồn tại")
                ],
            )
        ],
    )

    validated = enforce_evidence_policy(minutes)

    assert validated.action_items == []
