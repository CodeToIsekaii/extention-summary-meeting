# Summary Meeting Local

Extension Chrome ghi âm Google Meet; backend FastAPI chạy local; app desktop Tkinter quản lý recovery và resume AI. Model Whisper/Qwen, audio, cache và file tạm nằm trong `runtime` trên ổ D.

## Thành phần

- `apps/extension`: Manifest V3, TypeScript, React, Vite, capture và side panel.
- `apps/helper`: Python, FastAPI, Uvicorn, pipeline audio/Whisper/Qwen.
- `apps/desktop`: Python + Tkinter, tự mở backend và quản lý phiên recovery.
- `runtime`: models, meetings, work, logs, tmp.

## Quyết định

- Một phiên xử lý tại một thời điểm; người dùng chọn phiên để chạy.
- Chunk audio dài 30 giây.
- Resume theo stage và lưu checkpoint trên ổ D.
- Không lưu token, mật khẩu hoặc nội dung cuộc họp vào tài liệu AI.
