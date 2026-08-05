# Summary Meeting Local

Chrome extension ghi âm Google Meet và tạo biên bản tiếng Việt hoàn toàn trên laptop. Audio, model AI, cache và dữ liệu tạm nằm dưới `D:\MyProject\extention summary meeting\runtime` máy tôi còn máy bạn thì tự sửa theo ý bạn.

Nếu bạn quen tư duy fullstack, hãy hiểu đơn giản:

- `extension` = lớp giao diện và capture trong Chrome
- `backend local` = app chạy trên máy bạn để xử lý audio, AI, lưu file
- `Whisper` = engine speech-to-text
- `Qwen` = engine tóm tắt và trích xuất task

Tài liệu giải thích chi tiết, dễ đọc cho người mới nằm ở [docs/project-guide.vi.md](/abs/path/D:/MyProject/extention%20summary%20meeting/docs/project-guide.vi.md).
Sơ đồ kiến trúc và quy tắc phân loại thư mục nằm ở [docs/architecture.vi.md](/abs/path/D:/MyProject/extention%20summary%20meeting/docs/architecture.vi.md).

## Cài đặt

Mở PowerShell tại thư mục dự án:

```powershell
.\scripts\setup.ps1
.\scripts\install-models.ps1
```

Lệnh thứ hai tải khoảng 5 GB gồm Faster Whisper Medium, Qwen3 4B Q5_K_M và llama.cpp. Có thể dừng/chạy lại vì Hugging Face hỗ trợ tiếp tục tải.

Trên máy này các model đã được cài trong `runtime\models` trên ổ D (khoảng 4.16 GB). Việc đặt model/Whisper trên ổ D là hoàn toàn bình thường; backend local đã ép Hugging Face cache, TEMP, FFmpeg và file làm việc về `runtime` để không chiếm thêm ổ C.

## Chạy backend local

Nếu bạn dùng PowerShell:

```powershell
.\scripts\start-helper.ps1
```

Nếu bạn dùng Git Bash:

```bash
./scripts/start-helper.sh
```

Nếu dùng Windows và không muốn gõ lệnh, double-click file `scripts\start-backend.bat`.

Giữ cửa sổ backend local chạy trong lúc dùng extension.

## App desktop xử lý recovery

Mở `scripts\start-desktop.bat` để chạy Summary Meeting Manager. App tự khởi động backend local, liệt kê các phiên chưa hoàn tất và chỉ xử lý phiên bạn chọn bằng **Tiếp tục xử lý**. Không cần mở Google Meet hoặc side panel.

App lưu stage xử lý trên ổ D và có thể tiếp tục từ stage đã dừng sau khi tắt app hoặc máy. Chỉ một phiên được xử lý tại một thời điểm.

## Cài extension vào Chrome

1. Mở `chrome://extensions`.
2. Bật **Developer mode**.
3. Chọn **Load unpacked**.
4. Chọn `D:\MyProject\extention summary meeting\apps\extension\dist`.
5. Mở side panel Summary Meeting. Trong **Cài đặt backend local**, bấm **Ghép cặp tự động** (hoặc sao chép `auth_token` từ `config\settings.json` rồi dán vào ô token).

Hoặc mở một Chrome test riêng có profile/cache trên ổ D:

```powershell
.\scripts\launch-chrome-test.ps1
```

## Sử dụng

1. Chạy backend local và tham gia Google Meet.
2. Tự bật captions trong Meet để giữ tên người nói tốt hơn.
3. Mở side panel, nhập **Tên cuộc họp** (ví dụ `Họp dự án Website ABC`), rồi bấm **Bắt đầu ghi**. Chrome sẽ hỏi quyền microphone.
   Tên phòng kiểu `bpt-dpdd-moa` chỉ là mã Google Meet; nếu bỏ trống tên, extension mới dùng tiêu đề tab làm dự phòng.
4. Có thể bấm **Tóm tắt ngay**; AI chạy chậm ở chế độ ưu tiên máy mượt.
5. Bấm **Dừng và xử lý** trước khi rời phòng. Sau khi hoàn tất, mở biên bản từ side panel.

Trong lúc hậu xử lý có thể **Tạm dừng**, **Tiếp tục** hoặc chọn **Chế độ Nhanh**. Trang biên bản hỗ trợ sửa nội dung, tìm transcript, phát audio theo timestamp, **Chạy lại AI**, xuất Markdown và HTML.

Mỗi meeting hoàn chỉnh chỉ giữ `recording.webm` và `minutes.json` trong `runtime\meetings`.

### Cập nhật extension sau khi kéo code mới

Chạy build bằng Git Bash:

```bash
cd "/d/MyProject/extention summary meeting/apps/extension"
npm run build
```

Sau đó mở `chrome://extensions` và bấm **Reload** ở Summary Meeting Local. File ghi âm nằm tại `runtime\meetings\<tên-cuộc-họp>\recording.webm`; phiên lỗi tạm thời nằm trong `runtime\work` để có thể **Xử lý lại**.

## Kiểm thử

```powershell
.\scripts\verify.ps1
.\.venv\Scripts\python.exe .\scripts\smoke_models.py
.\.venv\Scripts\python.exe .\scripts\smoke_e2e.py
```

`verify.ps1` chạy unit test, lint và production build. Hai smoke script nạp model thật; `smoke_e2e.py` còn tạo một phiên giả lập qua toàn bộ API/pipeline. Việc cấp quyền tab/mic trong Google Meet thật cần kiểm tra thủ công vì Chrome không cho tự động hóa permission prompt ổn định.

Nếu cần dọn cache/generated files mà không đụng vào model, bản ghi hoặc recovery, dùng PowerShell:

```powershell
.\scripts\clean-generated.ps1 -WhatIf
.\scripts\clean-generated.ps1 -IncludePythonCaches
```

Muốn tạo lại thư mục `dist` sau khi dọn thì chạy `npm run build` trong `apps\extension`.

Sau khi ghi một cuộc Meet thật, kiểm tra file, schema, evidence, cleanup và khả năng giải mã audio bằng:

```powershell
.\scripts\validate-latest-meeting.ps1
```

## Quyền riêng tư

Backend local chỉ lắng nghe `127.0.0.1`. Không có cloud backend. Bạn chịu trách nhiệm thông báo và xin phép người tham gia trước khi ghi âm.
