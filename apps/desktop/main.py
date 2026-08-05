from __future__ import annotations

import json
import os
import subprocess
import threading
import tkinter as tk
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

    def process(self, session_id: str) -> dict:
        return self.request(f"/sessions/{session_id}/process", "POST")  # type: ignore[return-value]

    def pause(self, session_id: str) -> dict:
        return self.request(f"/sessions/{session_id}/pause", "POST")  # type: ignore[return-value]

    def resume(self, session_id: str) -> dict:
        return self.request(f"/sessions/{session_id}/resume", "POST")  # type: ignore[return-value]

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
        ttk.Button(actions, text="Tiếp tục xử lý", command=self._process).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Tạm dừng", command=self._pause).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Tiếp tục", command=self._resume).pack(side="left", padx=(0, 8))
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
                self.after(0, lambda: self._render(sessions))
            except OSError as error:
                message = str(error)
                self.after(0, lambda: self.status_var.set(f"Lỗi kết nối backend: {message}"))
        threading.Thread(target=load, daemon=True).start()

    def _render(self, sessions: list[dict]) -> None:
        self.rows = {item["id"]: item for item in sessions}
        self.table.delete(*self.table.get_children())
        for item in sessions:
            self.table.insert("", "end", iid=item["id"], values=(
                item.get("title", ""), item.get("status", ""),
                item.get("processing_stage") or "-", item.get("processing_progress", 0), item.get("error") or "",
            ))
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
