import type { MeetingMinutes } from "../shared/types";
import type { RecordingState } from "../shared/state";
import { formatTimestamp } from "../minutes/export";

interface RecordingPanelProps {
  state: RecordingState;
  helperReady: boolean;
  canStartWithDisk?: boolean;
  tokenConfigured: boolean;
  elapsedMs: number;
  checkpoint?: MeetingMinutes | null;
  processingPaused?: boolean;
  diskWarning?: string | null;
  onStart: () => void;
  onStop: () => void;
  onCheckpoint: () => void;
  onOpenMinutes: () => void;
  onPause?: () => void;
  onResume?: () => void;
  onFast?: () => void;
}

const phaseLabels: Record<RecordingState["phase"], string> = {
  idle: "Sẵn sàng",
  starting: "Đang khởi động…",
  recording: "Đang ghi",
  stopping: "Đang dừng…",
  processing: "Đang xử lý local…",
  completed: "Đã hoàn thành",
  error: "Có lỗi"
};

export function RecordingPanel({
  state,
  helperReady,
  canStartWithDisk = true,
  tokenConfigured,
  elapsedMs,
  checkpoint,
  processingPaused = false,
  diskWarning = null,
  onStart,
  onStop,
  onCheckpoint,
  onOpenMinutes,
  onPause,
  onResume,
  onFast
}: RecordingPanelProps) {
  const canStart =
    helperReady &&
    canStartWithDisk &&
    tokenConfigured &&
    ["idle", "error", "completed"].includes(state.phase);
  const isRecording = state.phase === "recording";

  return (
    <main className="panel-shell">
      <header className="panel-header">
        <div>
          <p className="eyebrow">LOCAL MEETING NOTES</p>
          <h1>Meet Assistant</h1>
        </div>
        <span className={`status-dot ${helperReady ? "is-online" : "is-offline"}`}>
          {helperReady ? "Helper sẵn sàng" : "Helper offline"}
        </span>
      </header>

      <section className={`recorder-card phase-${state.phase}`} aria-live="polite">
        <div className="recording-status">
          {isRecording ? <span className="rec-pill">REC</span> : <span className="phase-pill">{phaseLabels[state.phase]}</span>}
          <strong className="timer">{formatTimestamp(elapsedMs)}</strong>
        </div>
        <p className="status-copy">
          {isRecording
            ? "Audio tab và microphone đang được ghi trực tiếp về ổ D."
            : phaseLabels[state.phase]}
        </p>
        {state.error ? <p className="error-banner" role="alert">{state.error}</p> : null}
        {diskWarning ? <p className="warning-banner" role="alert">{diskWarning}</p> : null}
        {!tokenConfigured ? (
          <p className="warning-banner">Nhập token ghép cặp helper trong phần Cài đặt.</p>
        ) : null}

        <div className="primary-actions">
          {!isRecording ? (
            <button className="button button-primary" disabled={!canStart} onClick={onStart}>
              Bắt đầu ghi
            </button>
          ) : (
            <button className="button button-danger" onClick={onStop}>
              Dừng và xử lý
            </button>
          )}
          <button
            className="button button-secondary"
            disabled={!isRecording}
            onClick={onCheckpoint}
          >
            Tóm tắt ngay
          </button>
          {state.phase === "completed" ? (
            <button className="button button-secondary" onClick={onOpenMinutes}>
              Mở biên bản
            </button>
          ) : null}
          {state.phase === "processing" && onPause && onResume ? (
            <button
              className="button button-secondary"
              onClick={processingPaused ? onResume : onPause}
            >
              {processingPaused ? "Tiếp tục xử lý" : "Tạm dừng xử lý"}
            </button>
          ) : null}
          {state.phase === "processing" && !processingPaused && onFast ? (
            <button className="button button-secondary" onClick={onFast}>
              Chế độ Nhanh
            </button>
          ) : null}
        </div>
      </section>

      {checkpoint ? (
        <section className="checkpoint-card" aria-label="Tóm tắt tạm thời">
          <p className="eyebrow">CHECKPOINT</p>
          <h2>Tóm tắt tới hiện tại</h2>
          <p>{checkpoint.summary || "Chưa đủ nội dung để tóm tắt."}</p>
          <span>{checkpoint.action_items.length} công việc được phát hiện</span>
        </section>
      ) : null}
    </main>
  );
}
