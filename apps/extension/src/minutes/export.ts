import type { MeetingMinutes } from "../shared/types";

export function formatTimestamp(milliseconds: number): string {
  const totalSeconds = Math.floor(milliseconds / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return hours > 0
    ? [hours, minutes, seconds].map((value) => String(value).padStart(2, "0")).join(":")
    : [minutes, seconds].map((value) => String(value).padStart(2, "0")).join(":");
}

export function exportMarkdown(minutes: MeetingMinutes): string {
  const actionItems = minutes.action_items.length
    ? minutes.action_items
        .map((item) => {
          const checked = item.status === "completed" ? "x" : " ";
          const warning = item.status === "needs_confirmation" ? " ⚠️" : "";
          return `- [${checked}] ${item.task} — ${item.assignee ?? "Chưa xác định"} — ${item.deadline ?? "Chưa có deadline"}${warning}`;
        })
        .join("\n")
    : "Không có.";
  const transcript = minutes.transcript
    .map(
      (segment) =>
        `[${formatTimestamp(segment.start_ms)}] **${segment.speaker ?? "Chưa xác định"}:** ${segment.text}`
    )
    .join("\n\n");
  return `# ${minutes.title}\n\n## Tóm tắt\n\n${minutes.summary}\n\n## Quyết định\n\n${minutes.decisions.map((item) => `- ${item}`).join("\n") || "Không có."}\n\n## Công việc\n\n${actionItems}\n\n## Câu hỏi còn mở\n\n${minutes.open_questions.map((item) => `- ${item}`).join("\n") || "Không có."}\n\n## Transcript\n\n${transcript}\n`;
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[character]!);
}

export function exportHtml(minutes: MeetingMinutes): string {
  const decisions = minutes.decisions.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const tasks = minutes.action_items
    .map(
      (item) =>
        `<li><strong>${escapeHtml(item.task)}</strong> — ${escapeHtml(item.assignee ?? "Chưa xác định")} — ${escapeHtml(item.deadline ?? "Chưa có deadline")}${item.status === "needs_confirmation" ? " ⚠️" : ""}</li>`
    )
    .join("");
  const transcript = minutes.transcript
    .map(
      (item) =>
        `<p><time>${formatTimestamp(item.start_ms)}</time> <strong>${escapeHtml(item.speaker ?? "Chưa xác định")}</strong>: ${escapeHtml(item.text)}</p>`
    )
    .join("");
  return `<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>${escapeHtml(minutes.title)}</title><style>body{max-width:900px;margin:40px auto;padding:0 24px;font:16px/1.6 system-ui;color:#172033}h1{font-size:40px}section{margin:28px 0;padding-top:10px;border-top:1px solid #dfe4ec}time{color:#3157d5;font-variant-numeric:tabular-nums}</style></head><body><h1>${escapeHtml(minutes.title)}</h1><section><h2>Tóm tắt</h2><p>${escapeHtml(minutes.summary)}</p></section><section><h2>Quyết định</h2><ul>${decisions}</ul></section><section><h2>Công việc</h2><ul>${tasks}</ul></section><section><h2>Transcript</h2>${transcript}</section></body></html>`;
}
