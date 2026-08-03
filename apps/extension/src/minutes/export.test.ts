import { describe, expect, it } from "vitest";
import { exportHtml, exportMarkdown } from "./export";
import type { MeetingMinutes } from "../shared/types";

it("exports action items with confirmation markers and transcript timestamps", () => {
  const minutes: MeetingMinutes = {
    schema_version: 1,
    meeting_id: "meeting-1",
    title: "Daily",
    language: "vi",
    summary: "Nhóm kiểm tra tiến độ.",
    topics: [],
    decisions: [],
    action_items: [
      {
        task: "Kiểm tra log",
        assignee: null,
        deadline: null,
        status: "needs_confirmation",
        evidence: [{ timestamp_ms: 65000, speaker: "Lan", quote: "Cần kiểm tra log." }]
      }
    ],
    open_questions: [],
    participants: ["Lan"],
    transcript: [
      { start_ms: 65000, end_ms: 67000, speaker: "Lan", text: "Cần kiểm tra log.", source: "caption" }
    ]
  };

  const markdown = exportMarkdown(minutes);

  expect(markdown).toContain("- [ ] Kiểm tra log — Chưa xác định — Chưa có deadline ⚠️");
  expect(markdown).toContain("[01:05] **Lan:** Cần kiểm tra log.");
});

it("exports a self-contained escaped HTML meeting record", () => {
  const dangerous = {
    ...({
      schema_version: 1,
      meeting_id: "meeting-2",
      title: "Review <script>",
      language: "vi",
      summary: "A & B",
      topics: [],
      decisions: [],
      action_items: [],
      open_questions: [],
      participants: [],
      transcript: []
    } satisfies MeetingMinutes)
  };

  const html = exportHtml(dangerous);

  expect(html).toContain("Review &lt;script&gt;");
  expect(html).toContain("A &amp; B");
  expect(html).not.toContain("<script>");
});
