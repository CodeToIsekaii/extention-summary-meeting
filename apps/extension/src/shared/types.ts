export type AudioSource = "remote" | "me";
export type RecordingPhase =
  | "idle"
  | "starting"
  | "recording"
  | "stopping"
  | "processing"
  | "completed"
  | "error";

export interface CaptionSegment {
  start_ms: number;
  end_ms: number;
  speaker: string | null;
  text: string;
}

export interface TranscriptSegment extends CaptionSegment {
  source: "caption" | "stt_remote" | "stt_me" | "hybrid";
}

export interface Evidence {
  timestamp_ms: number;
  speaker: string | null;
  quote: string;
}

export interface ActionItem {
  task: string;
  assignee: string | null;
  deadline: string | null;
  status: "confirmed" | "needs_confirmation" | "completed";
  evidence: Evidence[];
}

export interface MeetingMinutes {
  schema_version: number;
  meeting_id: string;
  title: string;
  started_at?: string | null;
  ended_at?: string | null;
  duration_ms?: number | null;
  language: string;
  summary: string;
  topics: string[];
  decisions: string[];
  action_items: ActionItem[];
  open_questions: string[];
  participants: string[];
  transcript: TranscriptSegment[];
}

export interface ChunkEnvelope {
  source: AudioSource;
  sequence: number;
  startedAtMs?: number;
  durationMs: number;
  blob: Blob;
}
