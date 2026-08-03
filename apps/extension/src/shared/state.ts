import type { RecordingPhase } from "./types";

export interface RecordingState {
  phase: RecordingPhase;
  sessionId: string | null;
  startedAt: number | null;
  error: string | null;
}

export type RecordingAction =
  | { type: "START_REQUESTED" }
  | { type: "STARTED"; sessionId: string; startedAt: number }
  | { type: "STOP_REQUESTED" }
  | { type: "PROCESSING" }
  | { type: "COMPLETED" }
  | { type: "RESET" }
  | { type: "FAILED"; message: string };

export const initialRecordingState: RecordingState = {
  phase: "idle",
  sessionId: null,
  startedAt: null,
  error: null
};

export function recordingReducer(
  state: RecordingState,
  action: RecordingAction
): RecordingState {
  switch (action.type) {
    case "START_REQUESTED":
      if (state.phase !== "idle" && state.phase !== "error" && state.phase !== "completed") {
        throw new Error(`Cannot start from ${state.phase}`);
      }
      return { ...initialRecordingState, phase: "starting" };
    case "STARTED":
      if (state.phase !== "starting") throw new Error(`Cannot mark started from ${state.phase}`);
      return {
        phase: "recording",
        sessionId: action.sessionId,
        startedAt: action.startedAt,
        error: null
      };
    case "STOP_REQUESTED":
      if (state.phase !== "recording") throw new Error(`Cannot stop from ${state.phase}`);
      return { ...state, phase: "stopping" };
    case "PROCESSING":
      return { ...state, phase: "processing" };
    case "COMPLETED":
      return { ...state, phase: "completed", error: null };
    case "FAILED":
      return { ...state, phase: "error", error: action.message };
    case "RESET":
      return initialRecordingState;
  }
}
