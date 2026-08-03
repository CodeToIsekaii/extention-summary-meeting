# Meet Assistant Local

Chrome extension ghi âm Google Meet và tạo biên bản tiếng Việt hoàn toàn trên laptop. Audio, model AI, cache và dữ liệu tạm nằm dưới `D:\MyProject\extention summary meeting\runtime`.

## Cài đặt

Mở PowerShell tại thư mục dự án:

```powershell
.\scripts\setup.ps1
.\scripts\install-models.ps1
```

Lệnh thứ hai tải khoảng 5 GB gồm Faster Whisper Medium, Qwen3 4B Q5_K_M và llama.cpp. Có thể dừng/chạy lại vì Hugging Face hỗ trợ tiếp tục tải.

Trên máy này các model đã được cài trong `runtime\models` trên ổ D (khoảng 4.16 GB). Việc đặt model/Whisper trên ổ D là hoàn toàn bình thường; helper đã ép Hugging Face cache, TEMP, FFmpeg và file làm việc về `runtime` để không chiếm thêm ổ C.

## Chạy helper

```powershell
.\scripts\start-helper.ps1
```

Giữ cửa sổ helper chạy trong lúc dùng extension.

## Cài extension vào Chrome

1. Mở `chrome://extensions`.
2. Bật **Developer mode**.
3. Chọn **Load unpacked**.
4. Chọn `D:\MyProject\extention summary meeting\apps\extension\dist`.
5. Mở side panel Meet Assistant, mở `config\settings.json`, sao chép `auth_token` và dán vào **Cài đặt helper**.

## Sử dụng

1. Chạy helper và tham gia Google Meet.
2. Tự bật captions trong Meet để giữ tên người nói tốt hơn.
3. Mở side panel và bấm **Bắt đầu ghi**. Chrome sẽ hỏi quyền microphone.
4. Có thể bấm **Tóm tắt ngay**; AI chạy chậm ở chế độ ưu tiên máy mượt.
5. Bấm **Dừng và xử lý** trước khi rời phòng. Sau khi hoàn tất, mở biên bản từ side panel.

Trong lúc hậu xử lý có thể **Tạm dừng**, **Tiếp tục** hoặc chọn **Chế độ Nhanh**. Trang biên bản hỗ trợ sửa nội dung, tìm transcript, phát audio theo timestamp, **Chạy lại AI**, xuất Markdown và HTML.

Mỗi meeting hoàn chỉnh chỉ giữ `recording.webm` và `minutes.json` trong `runtime\meetings`.

## Kiểm thử

```powershell
.\scripts\verify.ps1
.\.venv\Scripts\python.exe .\scripts\smoke_models.py
.\.venv\Scripts\python.exe .\scripts\smoke_e2e.py
```

`verify.ps1` chạy unit test, lint và production build. Hai smoke script nạp model thật; `smoke_e2e.py` còn tạo một phiên giả lập qua toàn bộ API/pipeline. Việc cấp quyền tab/mic trong Google Meet thật cần kiểm tra thủ công vì Chrome không cho tự động hóa permission prompt ổn định.

## Quyền riêng tư

Helper chỉ lắng nghe `127.0.0.1`. Không có cloud backend. Bạn chịu trách nhiệm thông báo và xin phép người tham gia trước khi ghi âm.
