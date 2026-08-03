import { useMemo, useRef, useState } from "react";
import { exportHtml, exportMarkdown, formatTimestamp } from "./export";
import type { MeetingMinutes } from "../shared/types";

interface MinutesEditorProps {
  initialMinutes: MeetingMinutes;
  audioUrl: string | null;
  onSave: (minutes: MeetingMinutes) => void | Promise<void>;
  onRegenerate?: () => MeetingMinutes | Promise<MeetingMinutes>;
}

function downloadText(filename: string, text: string, type: string): void {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function MinutesEditor({ initialMinutes, audioUrl, onSave, onRegenerate }: MinutesEditorProps) {
  const [minutes, setMinutes] = useState(initialMinutes);
  const [query, setQuery] = useState("");
  const [saving, setSaving] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const audioRef = useRef<HTMLAudioElement>(null);
  const transcript = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("vi");
    if (!normalized) return minutes.transcript;
    return minutes.transcript.filter(
      (item) =>
        item.text.toLocaleLowerCase("vi").includes(normalized) ||
        item.speaker?.toLocaleLowerCase("vi").includes(normalized)
    );
  }, [minutes.transcript, query]);

  const save = async () => {
    setSaving(true);
    try {
      await onSave(minutes);
    } finally {
      setSaving(false);
    }
  };

  const regenerate = async () => {
    if (!onRegenerate) return;
    setRegenerating(true);
    try {
      setMinutes(await onRegenerate());
    } finally {
      setRegenerating(false);
    }
  };

  const seek = (timestampMs: number) => {
    if (!audioRef.current) return;
    audioRef.current.currentTime = timestampMs / 1000;
    void audioRef.current.play();
  };

  return (
    <main className="minutes-shell">
      <header className="minutes-header">
        <div>
          <p className="eyebrow">MEETING RECORD</p>
          <input
            className="title-input"
            aria-label="Tiêu đề"
            value={minutes.title}
            onChange={(event) => setMinutes({ ...minutes, title: event.target.value })}
          />
          <p>{minutes.participants.join(" · ") || "Chưa nhận diện người tham gia"}</p>
        </div>
        <div className="header-actions">
          {onRegenerate ? (
            <button className="button button-secondary" disabled={regenerating} onClick={regenerate}>
              {regenerating ? "AI đang chạy…" : "Chạy lại AI"}
            </button>
          ) : null}
          <button className="button button-secondary" onClick={() => downloadText("minutes.md", exportMarkdown(minutes), "text/markdown")}>
            Xuất Markdown
          </button>
          <button className="button button-secondary" onClick={() => downloadText("minutes.html", exportHtml(minutes), "text/html")}>
            Xuất HTML
          </button>
          <button className="button button-primary" disabled={saving} onClick={save}>
            {saving ? "Đang lưu…" : "Lưu thay đổi"}
          </button>
        </div>
      </header>

      {audioUrl ? <audio ref={audioRef} className="audio-player" src={audioUrl} controls /> : null}

      <div className="minutes-grid">
        <section className="surface summary-surface">
          <label htmlFor="summary">Tóm tắt</label>
          <textarea
            id="summary"
            value={minutes.summary}
            onChange={(event) => setMinutes({ ...minutes, summary: event.target.value })}
          />
        </section>

        <section className="surface">
          <h2>Quyết định</h2>
          {minutes.decisions.length ? (
            <ul>{minutes.decisions.map((decision) => <li key={decision}>{decision}</li>)}</ul>
          ) : <p className="empty-copy">Chưa phát hiện quyết định rõ ràng.</p>}
        </section>

        <section className="surface action-surface">
          <h2>Công việc</h2>
          <div className="task-list">
            {minutes.action_items.map((item, index) => (
              <article className="task-card" key={`${item.task}-${index}`}>
                <div className="task-heading">
                  <input
                    type="checkbox"
                    aria-label={`Hoàn thành ${item.task}`}
                    checked={item.status === "completed"}
                    onChange={(event) => {
                      const action_items = [...minutes.action_items];
                      action_items[index] = {
                        ...item,
                        status: event.target.checked ? "completed" : item.assignee && item.deadline ? "confirmed" : "needs_confirmation"
                      };
                      setMinutes({ ...minutes, action_items });
                    }}
                  />
                  <strong>{item.task}</strong>
                  {item.status === "needs_confirmation" ? <span className="warning-badge">Cần xác nhận</span> : null}
                </div>
                <p>{item.assignee ?? "Chưa xác định"} · {item.deadline ?? "Chưa có deadline"}</p>
                {item.evidence[0] ? (
                  <button className="evidence" onClick={() => seek(item.evidence[0].timestamp_ms)}>
                    {formatTimestamp(item.evidence[0].timestamp_ms)} — “{item.evidence[0].quote}”
                  </button>
                ) : null}
              </article>
            ))}
            {!minutes.action_items.length ? <p className="empty-copy">Không có công việc có đủ bằng chứng.</p> : null}
          </div>
        </section>

        <section className="surface transcript-surface">
          <div className="section-heading">
            <h2>Transcript</h2>
            <input
              type="search"
              aria-label="Tìm transcript"
              placeholder="Tìm nội dung hoặc người nói"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          <div className="transcript-list">
            {transcript.map((segment, index) => (
              <article className="transcript-row" key={`${segment.start_ms}-${index}`}>
                <button onClick={() => seek(segment.start_ms)}>{formatTimestamp(segment.start_ms)}</button>
                <div><strong>{segment.speaker ?? "Chưa xác định"}</strong><p>{segment.text}</p></div>
              </article>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
