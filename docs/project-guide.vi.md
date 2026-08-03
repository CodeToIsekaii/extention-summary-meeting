# Summary Meeting Local

Tài liệu này giải thích dự án theo cách dễ hiểu cho người làm fullstack, không giả định bạn đã quen với AI local.

## Dự án này làm gì

Mục tiêu của dự án là:

- ghi âm Google Meet trên máy Windows
- lấy cả tiếng từ tab Meet và microphone của bạn
- giữ captions nếu Meet đang bật phụ đề
- sau cuộc họp, tự tạo biên bản tiếng Việt
- trích xuất task, owner, deadline, quyết định, rủi ro
- lưu mọi dữ liệu quan trọng trên ổ `D:`

Kết quả cuối mỗi cuộc họp chỉ còn:

- `recording.webm`
- `minutes.json`

## Kiến trúc dễ hiểu

Nếu nhìn bằng tư duy fullstack, hệ thống này có 2 phần chính:

1. `Chrome Extension`
2. `Backend Local`

### 1. Chrome Extension làm gì

Extension là phần chạy trong Chrome. Nó chịu trách nhiệm:

- hiện giao diện side panel
- cho bạn bấm `Bắt đầu ghi` và `Dừng`
- lấy audio từ tab Google Meet
- lấy audio từ microphone
- đọc captions trên trang Meet
- gửi dữ liệu sang backend local

Bạn có thể xem nó như frontend + lớp capture.

### 2. Backend Local làm gì

Backend local là app chạy trên chính máy bạn. Nó chịu trách nhiệm:

- nhận audio chunk từ extension
- ghi file tạm vào `runtime\work`
- quản lý dung lượng ổ `D:`
- gọi model AI để phiên âm và tóm tắt
- ghép audio cuối cùng
- sinh `minutes.json`
- dọn dữ liệu trung gian
- giữ phiên recovery nếu bị crash hoặc mất điện

Bạn có thể xem nó như backend API nội bộ chỉ chạy trên `127.0.0.1`.

## Vì sao cần backend local

Chrome extension không phải desktop app full quyền. Nó không phù hợp để:

- chạy model AI nặng nhiều phút hoặc nhiều giờ
- kiểm soát RAM và CPU chặt
- ghi file lớn bền vững vào ổ `D:`
- làm hậu xử lý audio bằng `ffmpeg`
- đảm bảo retry và recovery sau lỗi

Vì vậy extension chỉ nên lo phần giao diện và capture, còn xử lý nặng giao cho backend local.

## AI trong dự án hoạt động thế nào

Có 2 loại model chính:

- `Whisper`: đổi audio thành chữ
- `Qwen`: đọc transcript rồi viết biên bản

Bạn không cần học AI theo kiểu nghiên cứu. Chỉ cần hiểu 3 lớp:

1. `model`
2. `runtime`
3. `app code`

### Model là gì

Model là file dữ liệu đã được huấn luyện sẵn. Nó giống như "bộ não" của AI, nhưng bản thân file model không tự chạy được.

Ví dụ trong dự án:

- Whisper model
- Qwen model

### Runtime là gì

Runtime là chương trình hoặc thư viện đọc file model rồi chạy nó.

Ví dụ:

- `faster-whisper` là runtime để chạy Whisper trong Python
- `llama.cpp` là runtime để chạy model GGUF như Qwen trên máy local

### App code là gì

App code là code của dự án bạn viết ra để điều phối pipeline:

- nhận audio
- gọi Whisper
- gọi Qwen
- lưu file
- xử lý lỗi

Trong dự án này, app code đó chủ yếu nằm ở backend local.

## Giải thích thuật ngữ ngắn gọn

- `Whisper`: model speech-to-text
- `Qwen`: model ngôn ngữ dùng để tóm tắt và rút task
- `GGUF`: định dạng file model cho LLM local
- `llama.cpp`: runtime chạy model GGUF
- `faster-whisper`: thư viện Python chạy Whisper hiệu quả hơn bản gốc cho use case này
- `checkpoint`: bản tóm tắt tạm trong lúc họp
- `recovery`: dữ liệu cứu phiên khi app lỗi giữa chừng

## Luồng dữ liệu của một cuộc họp

1. Bạn mở Google Meet
2. Extension lấy audio tab + mic + captions
3. Extension gửi chunk sang backend local
4. Backend local ghi chunk vào `runtime\work`
5. Khi bấm dừng, backend local chạy phiên âm bằng Whisper
6. Backend local đưa transcript vào Qwen để tạo biên bản
7. Backend local ghép audio cuối cùng
8. Kết quả được lưu vào `runtime\meetings\<session>`
9. Dữ liệu tạm bị xóa nếu phiên thành công

## Thư mục chính

```text
D:\MyProject\extention summary meeting\
├── apps\
│   ├── extension\
│   └── helper\
├── runtime\
│   ├── models\
│   ├── meetings\
│   ├── work\
│   ├── logs\
│   └── tmp\
└── config\
    └── settings.json
```

Lưu ý:

- thư mục code vẫn đang là `apps\helper`
- trong tài liệu và UI, ta gọi nó là `backend local`
- đây là đổi cách gọi để dễ hiểu hơn, không phải refactor toàn bộ package name

## Cách cài và chạy

### Bước 1: setup project

Mở PowerShell trong thư mục dự án:

```powershell
.\scripts\setup.ps1
```

Script này sẽ:

- tạo `.venv`
- cài Python dependencies
- cài Node dependencies cho extension
- tạo `config\settings.json`
- tạo token ghép cặp
- tạo thư mục runtime trên ổ `D:`

### Bước 2: tải model

```powershell
.\scripts\install-models.ps1
```

Model sẽ nằm trong `runtime\models`.

### Bước 3: chạy backend local

```powershell
.\scripts\start-helper.ps1
```

Tên script vẫn là `start-helper.ps1` vì code hiện tại chưa đổi package name. Nhưng về mặt khái niệm, đây là lệnh khởi động backend local.

### Bước 4: build extension nếu cần

Nếu `setup.ps1` đã chạy xong thì thường đã build sẵn. Nếu cần build lại:

```powershell
cd apps\extension
npm run build
```

### Bước 5: cài extension vào Chrome

1. Mở `chrome://extensions`
2. Bật `Developer mode`
3. Bấm `Load unpacked`
4. Chọn thư mục `D:\MyProject\extention summary meeting\apps\extension\dist`
5. Ghim extension nếu muốn
6. Mở Google Meet
7. Mở side panel của extension
8. Mở `config\settings.json`, copy `auth_token`
9. Dán token đó vào phần `Cài đặt backend local`

## Dùng hằng ngày

1. Chạy backend local
2. Vào Google Meet
3. Bật captions trong Meet nếu muốn nhận diện người nói tốt hơn
4. Mở extension side panel
5. Dán token nếu chưa cấu hình
6. Bấm `Bắt đầu ghi`
7. Cuối cuộc họp bấm `Dừng và xử lý`
8. Mở biên bản khi xử lý xong

## CPU, RAM và context dùng để làm gì

### CPU

CPU dùng cho:

- encode/decode audio
- xử lý chunk
- chạy Whisper trên CPU
- chạy Qwen qua `llama.cpp`
- ghép file bằng `ffmpeg`
- validate output cuối

### RAM

RAM dùng cho:

- nạp model vào bộ nhớ
- giữ context của prompt
- buffer audio/transcript tạm
- dữ liệu trung gian khi model đang suy luận

Hiện cấu hình mục tiêu là khoảng `5 GB RAM` cho backend local.

### Context

Context là lượng nội dung model được đọc trong một lượt suy luận.

Hiểu đơn giản:

- context nhỏ hơn: ít RAM hơn, nhanh hơn, nhưng dễ mất thông tin xa
- context lớn hơn: giữ được nhiều transcript hơn, nhưng tốn RAM hơn và chậm hơn

Trong project hiện tại, context phía tóm tắt đã được nâng lên mức vừa phải để cân bằng với giới hạn RAM 5 GB.

## Khi nào bạn cần học sâu hơn

Bạn chỉ cần học sâu hơn nếu muốn tự thay model hoặc tối ưu nặng. Còn để build MVP, bạn chỉ cần nắm:

- extension lấy dữ liệu thế nào
- backend local nhận và lưu ra sao
- Whisper nhận audio và trả transcript
- Qwen nhận transcript và trả biên bản
- lỗi thì recovery thế nào

## Tên gọi trong dự án

Để dễ hiểu hơn, nên dùng các tên này khi trao đổi:

- tên sản phẩm: `Summary Meeting Local`
- phần Chrome: `extension`
- phần chạy trên máy: `backend local`

Trong code hiện tại, nhiều chỗ vẫn dùng từ `helper`. Điều đó không sai; nó chỉ là tên kỹ thuật cũ.
