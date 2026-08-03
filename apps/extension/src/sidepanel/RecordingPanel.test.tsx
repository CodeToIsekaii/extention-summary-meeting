import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { RecordingPanel } from "./RecordingPanel";
import { initialRecordingState } from "../shared/state";

it("starts only from an explicit user click when helper and token are ready", () => {
  const start = vi.fn();
  render(
    <RecordingPanel
      state={initialRecordingState}
      helperReady
      tokenConfigured
      elapsedMs={0}
      onStart={start}
      onStop={() => undefined}
      onCheckpoint={() => undefined}
      onOpenMinutes={() => undefined}
    />
  );

  fireEvent.click(screen.getByRole("button", { name: "Bắt đầu ghi" }));

  expect(start).toHaveBeenCalledTimes(1);
});

it("shows a persistent REC indicator while recording", () => {
  render(
    <RecordingPanel
      state={{
        ...initialRecordingState,
        phase: "recording",
        sessionId: "session-1",
        startedAt: Date.now() - 65000
      }}
      helperReady
      tokenConfigured
      elapsedMs={65000}
      onStart={() => undefined}
      onStop={() => undefined}
      onCheckpoint={() => undefined}
      onOpenMinutes={() => undefined}
    />
  );

  expect(screen.getByText("REC")).toBeVisible();
  expect(screen.getByText("01:05")).toBeVisible();
  expect(screen.getByRole("button", { name: "Dừng và xử lý" })).toBeEnabled();
});
