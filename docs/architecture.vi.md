# Kiến trúc Summary Meeting Local

## Cây thư mục chính

```text
extention summary meeting/
├── apps/
│   ├── extension/     # Chrome Extension: giao diện và capture Meet
│   ├── helper/        # Backend local: API, audio, Whisper, Qwen
│   └── desktop/       # App Tkinter: recovery và điều khiển xử lý
├── runtime/           # Dữ liệu chạy thật, luôn nằm trên ổ D
│   ├── models/        # Whisper, Qwen, llama.cpp
│   ├── meetings/      # Kết quả cuối: recording.webm + minutes.json
│   ├── work/          # Chunk và checkpoint của phiên chưa hoàn tất
│   ├── logs/          # helper.log và desktop-backend.log
│   └── tmp/           # File tạm/FFmpeg
├── config/            # settings.example.json và settings.json cục bộ
├── scripts/           # Setup, build, verify và launcher Windows/Git Bash
├── docs/              # Tài liệu cho người dùng và developer
├── .codex/            # Quy tắc, memory, agent và skill cho AI
├── AGENTS.md          # Điểm vào quy tắc Codex
├── README.md
└── .gitignore
```

## Luồng dữ liệu

```text
Google Meet
    │
    ▼
Chrome Extension ── audio chunks/captions ──► Backend local
                                                │
                                                ├─ runtime/work
                                                ├─ Whisper
                                                ├─ Qwen
                                                └─ runtime/meetings
                                                       │
                                                       ├─ recording.webm
                                                       └─ minutes.json

Desktop Manager ── API process/pause/resume ──► Backend local
```

## Source và generated files

Source cần commit gồm `apps/*/src`, `apps/desktop`, `scripts`, `config/settings.example.json`, `docs`, `.codex` và các file cấu hình.

Generated/local files không commit gồm `node_modules`, `dist`, `.venv`, `__pycache__`, cache test, model, audio, log và `config/settings.json`.

## Quy tắc không nhầm thư mục

- Muốn sửa chức năng Chrome: vào `apps/extension/src`.
- Muốn sửa API/AI/audio: vào `apps/helper/src/meet_assistant`.
- Muốn sửa app quản lý recovery: vào `apps/desktop/main.py`.
- Muốn tìm bản ghi: vào `runtime/meetings`.
- Muốn tìm phiên lỗi để xử lý lại: vào `runtime/work` hoặc mở Desktop Manager.
- Không xóa `runtime/work` thủ công nếu còn muốn recovery.
