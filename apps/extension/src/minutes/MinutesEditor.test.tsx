import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { MinutesEditor } from "./MinutesEditor";
import type { MeetingMinutes } from "../shared/types";

const minutes: MeetingMinutes = {
  schema_version: 1,
  meeting_id: "meeting-1",
  title: "Planning",
  language: "vi",
  summary: "Bản đầu",
  topics: [],
  decisions: [],
  action_items: [
    {
      task: "Gửi báo cáo",
      assignee: null,
      deadline: null,
      status: "needs_confirmation",
      evidence: [{ timestamp_ms: 1000, speaker: "Lan", quote: "Cần gửi báo cáo." }]
    }
  ],
  open_questions: [],
  participants: ["Lan"],
  transcript: []
};

it("surfaces unconfirmed task fields and saves edited summary", () => {
  const save = vi.fn();
  render(<MinutesEditor initialMinutes={minutes} audioUrl={null} onSave={save} />);

  expect(screen.getByText("Cần xác nhận")).toBeVisible();
  fireEvent.change(screen.getByLabelText("Tóm tắt"), { target: { value: "Bản đã sửa" } });
  fireEvent.click(screen.getByRole("button", { name: "Lưu thay đổi" }));

  expect(save).toHaveBeenCalledWith(expect.objectContaining({ summary: "Bản đã sửa" }));
});
