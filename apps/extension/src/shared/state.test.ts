import { describe, expect, it } from "vitest";
import { initialRecordingState, recordingReducer } from "./state";

describe("recordingReducer", () => {
  it("allows the deliberate idle to recording lifecycle", () => {
    const starting = recordingReducer(initialRecordingState, { type: "START_REQUESTED" });
    const recording = recordingReducer(starting, {
      type: "STARTED",
      sessionId: "session-1",
      startedAt: 1000
    });

    expect(starting.phase).toBe("starting");
    expect(recording).toMatchObject({
      phase: "recording",
      sessionId: "session-1",
      startedAt: 1000,
      error: null
    });
  });

  it("moves to stopped with an explicit error when the helper buffer expires", () => {
    const recording = {
      ...initialRecordingState,
      phase: "recording" as const,
      sessionId: "session-1",
      startedAt: 1000
    };

    const failed = recordingReducer(recording, {
      type: "FAILED",
      message: "Không thể kết nối helper trong 30 giây."
    });

    expect(failed.phase).toBe("error");
    expect(failed.error).toContain("30 giây");
  });

  it("rejects a second start while already recording", () => {
    const recording = {
      ...initialRecordingState,
      phase: "recording" as const,
      sessionId: "session-1"
    };

    expect(() => recordingReducer(recording, { type: "START_REQUESTED" })).toThrow(
      "Cannot start from recording"
    );
  });
});
