from __future__ import annotations

import json
import html
import os
import subprocess
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
API = "http://127.0.0.1:8765/v1"


def auth_token() -> str:
    settings = ROOT / "config" / "settings.json"
    if settings.is_file():
        try:
            return str(json.loads(settings.read_text(encoding="utf-8")).get("auth_token", ""))
        except (OSError, ValueError):
            pass
    return "development-token-change-me"


class BackendClient:
    def __init__(self) -> None:
        self.token = auth_token()

    def request(self, path: str, method: str = "GET") -> object:
        request = Request(
            f"{API}{path}",
            method=method,
            headers={"Authorization": f"Bearer {self.token}"},
        )
        with urlopen(request, timeout=10) as response:
            if response.status == 204:
                return None
            return json.loads(response.read().decode("utf-8"))

    def health(self) -> dict:
        return self.request("/health", "GET")  # type: ignore[return-value]

    def sessions(self) -> list[dict]:
        return self.request("/sessions", "GET")  # type: ignore[return-value]

    def meetings(self) -> list[dict]:
        return self.request("/meetings", "GET")  # type: ignore[return-value]

    def minutes(self, meeting_id: str) -> dict:
        return self.request(f"/sessions/{meeting_id}/minutes", "GET")  # type: ignore[return-value]

    def process(self, session_id: str) -> dict:
        return self.request(f"/sessions/{session_id}/process", "POST")  # type: ignore[return-value]

    def pause(self, session_id: str) -> dict:
        return self.request(f"/sessions/{session_id}/pause", "POST")  # type: ignore[return-value]

    def resume(self, session_id: str) -> dict:
        return self.request(f"/sessions/{session_id}/resume", "POST")  # type: ignore[return-value]

    def fast(self, session_id: str) -> dict:
        return self.request(f"/sessions/{session_id}/fast", "POST")  # type: ignore[return-value]

    def delete(self, session_id: str) -> None:
        self.request(f"/sessions/{session_id}", "DELETE")


class DesktopApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Summary Meeting Manager")
        self.geometry("920x700")
        self.minsize(760, 560)
        self.client = BackendClient()
        self.backend: subprocess.Popen[bytes] | None = None
        self.log_handle = None
        self.log_path = ROOT / "runtime" / "logs" / "desktop-backend.log"
        self.rows: dict[str, dict] = {}
        self.selected_id: str | None = None
        self.status_var = tk.StringVar(value="Đang khởi động backend local…")
        self.progress_var = tk.StringVar(value="Chưa chọn phiên")
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._start_backend()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Summary Meeting Manager", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w", pady=(2, 12))
        columns = ("title", "status", "stage", "progress", "error")
        self.table = ttk.Treeview(outer, columns=columns, show="headings", height=14)
        headings = {"title": "Cuộc họp", "status": "Trạng thái", "stage": "Bước", "progress": "%", "error": "Lỗi"}
        widths = {"title": 220, "status": 100, "stage": 130, "progress": 55, "error": 220}
        for column in columns:
            self.table.heading(column, text=headings[column])
            self.table.column(column, width=widths[column], anchor="w")
        self.table.pack(fill="both", expand=True)
        self.table.bind("<<TreeviewSelect>>", self._select)
        ttk.Label(outer, textvariable=self.progress_var).pack(anchor="w", pady=8)
        actions = ttk.Frame(outer)
        actions.pack(fill="x")
        ttk.Button(actions, text="Bắt đầu / xử lý lại", command=self._process).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Tạm dừng", command=self._pause).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Tiếp tục sau tạm dừng", command=self._resume).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Chế độ Nhanh", command=self._fast).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Xem biên bản AI", command=self._open_minutes).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Xóa recovery", command=self._delete).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Làm mới", command=self.refresh).pack(side="right")
        log_frame = ttk.LabelFrame(outer, text="Nhật ký backend local", padding=6)
        log_frame.pack(fill="both", expand=True, pady=(12, 0))
        self.log_text = tk.Text(log_frame, height=8, state="disabled", wrap="none", font=("Consolas", 9))
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        log_scroll.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.after(1500, self.refresh_log)

    def _start_backend(self) -> None:
        try:
            self.client.health()
            self.status_var.set("Backend local đang chạy")
        except OSError:
            if not PYTHON.is_file():
                self.status_var.set("Thiếu .venv; hãy chạy scripts/setup.ps1 trước")
                return
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT / "apps" / "helper" / "src")
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self.log_handle = self.log_path.open("ab")
            self.backend = subprocess.Popen(
                [str(PYTHON), "-m", "meet_assistant.main"],
                cwd=str(ROOT),
                env=env,
                creationflags=(
                    getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                    | getattr(subprocess, "CREATE_NO_WINDOW", 0)
                ),
                stdin=subprocess.DEVNULL,
                stdout=self.log_handle,
                stderr=subprocess.STDOUT,
            )
            self._wait_for_backend()

    def _wait_for_backend(self, attempts: int = 30) -> None:
        try:
            self.client.health()
            self.status_var.set("Backend local đang chạy")
            self.refresh()
            return
        except OSError:
            if attempts <= 0:
                self.status_var.set("Không kết nối được backend local")
                return
            self.after(500, lambda: self._wait_for_backend(attempts - 1))

    def refresh(self) -> None:
        def load() -> None:
            try:
                sessions = self.client.sessions()
                meetings = self.client.meetings()
                self.after(0, lambda: self._render(sessions, meetings))
            except OSError as error:
                message = str(error)
                self.after(0, lambda: self.status_var.set(f"Lỗi kết nối backend: {message}"))
        threading.Thread(target=load, daemon=True).start()

    def _render(self, sessions: list[dict], meetings: list[dict]) -> None:
        selected_id = self.selected_id
        completed = [
            {
                **item,
                "status": "completed",
                "processing_stage": "completed",
                "processing_progress": 100,
                "error": None,
            }
            for item in meetings
        ]
        all_items = sessions + completed
        self.rows = {item["id"]: item for item in all_items}
        self.table.delete(*self.table.get_children())
        for item in all_items:
            self.table.insert("", "end", iid=item["id"], values=(
                item.get("title", ""), item.get("status", ""),
                item.get("processing_stage") or "-", item.get("processing_progress", 0), item.get("error") or "",
            ))
        if selected_id and selected_id in self.rows:
            self.table.selection_set(selected_id)
            self.table.focus(selected_id)
            self.selected_id = selected_id
        self.after(3000, self.refresh)

    def refresh_log(self) -> None:
        try:
            content = self.log_path.read_text(encoding="utf-8", errors="replace")
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.insert("end", "\n".join(content.splitlines()[-120:]))
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        except OSError:
            pass
        self.after(1500, self.refresh_log)

    def _select(self, _event: object = None) -> None:
        selected = self.table.selection()
        self.selected_id = selected[0] if selected else None
        item = self.rows.get(self.selected_id or "")
        if item:
            self.progress_var.set(f"{item.get('processing_stage') or '-'} · {item.get('processing_progress', 0)}%")

    def _run_action(self, action, success: str) -> None:
        if not self.selected_id:
            messagebox.showinfo("Chọn phiên", "Hãy chọn một phiên trong danh sách trước.")
            return
        selected = self.rows.get(self.selected_id)
        if selected and selected.get("status") == "completed":
            messagebox.showinfo(
                "Cuộc họp đã hoàn tất",
                "Cuộc họp này đã được lưu trong runtime\\meetings; không cần xử lý lại.",
            )
            return
        session_id = self.selected_id
        try:
            action(session_id)
            self.status_var.set(success)
            self.refresh()
        except OSError as error:
            messagebox.showerror("Backend local", str(error))

    def _process(self) -> None:
        self._run_action(self.client.process, "Đã bắt đầu/tiếp tục xử lý phiên")

    def _pause(self) -> None:
        self._run_action(self.client.pause, "Đã tạm dừng phiên")

    def _resume(self) -> None:
        self._run_action(self.client.resume, "Đã tiếp tục phiên")

    def _fast(self) -> None:
        self._run_action(self.client.fast, "Đã bật Chế độ Nhanh")

    def _open_minutes(self) -> None:
        if not self.selected_id:
            messagebox.showinfo("Chọn cuộc họp", "Hãy chọn cuộc họp đã hoàn tất trước.")
            return
        selected = self.rows.get(self.selected_id)
        output_dir = selected.get("output_dir") if selected else None
        if not output_dir:
            messagebox.showinfo(
                "Chưa có biên bản",
                "Cuộc họp này chưa có biên bản hoàn tất để mở.",
            )
            return
        try:
            minutes = self.client.minutes(self.selected_id)
            output_path = Path(output_dir)
            audio_uri = (output_path / "recording.webm").as_uri()
            def item_list(values: list[str]) -> str:
                return "".join(f"<li>{html.escape(str(value))}</li>" for value in values) or "<li>Không có.</li>"
            transcript = "".join(
                f"<p><time>{int(item.get('start_ms', 0)) // 1000}s</time> "
                f"<strong>{html.escape(str(item.get('speaker') or 'Chưa xác định'))}:</strong> "
                f"{html.escape(str(item.get('text', '')))}</p>"
                for item in minutes.get("transcript", [])
            ) or "<p>Không có transcript.</p>"
            view_path = Path(self.log_path).parent.parent / "tmp" / f"minutes-view-{self.selected_id}.html"
            view_path.parent.mkdir(parents=True, exist_ok=True)
            title = html.escape(str(minutes.get("title", "Biên bản cuộc họp")))
            view_path.write_text(
                "<!doctype html><html lang='vi'><meta charset='utf-8'>"
                "<meta name='viewport' content='width=device-width,initial-scale=1'>"
                f"<title>{title}</title><style>body{{max-width:960px;margin:32px auto;padding:0 24px;font:16px/1.6 Segoe UI,Arial;color:#172033}}"
                "h1{color:#153a9b}section{margin:24px 0;padding:20px;border:1px solid #dfe4ec;border-radius:14px}"
                "time{color:#3157d5;margin-right:8px}audio{width:100%}</style>"
                f"<h1>{title}</h1><section><h2>Tóm tắt</h2><p>{html.escape(str(minutes.get('summary', '')))}</p></section>"
                f"<section><h2>Quyết định</h2><ul>{item_list(minutes.get('decisions', []))}</ul></section>"
                f"<section><h2>Công việc</h2><ul>{item_list([str(item.get('task', item)) for item in minutes.get('action_items', [])])}</ul></section>"
                f"<section><h2>Câu hỏi còn mở</h2><ul>{item_list(minutes.get('open_questions', []))}</ul></section>"
                f"<section><h2>Audio</h2><audio controls src='{audio_uri}'></audio></section>"
                f"<section><h2>Transcript</h2>{transcript}</section></html>",
                encoding="utf-8",
            )
            webbrowser.open(view_path.as_uri())
        except OSError as error:
            messagebox.showerror("Không mở được biên bản AI", str(error))

    def _delete(self) -> None:
        if not self.selected_id or not messagebox.askyesno("Xóa recovery", "Xóa toàn bộ dữ liệu tạm của phiên này?"):
            return
        self._run_action(self.client.delete, "Đã xóa phiên recovery")

    def _close(self) -> None:
        if self.backend and self.backend.poll() is None:
            self.backend.terminate()
        if self.log_handle:
            self.log_handle.close()
        self.destroy()


if __name__ == "__main__":
    DesktopApp().mainloop()
