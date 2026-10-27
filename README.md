# Review Studio 0.8

Dựng video review 9:16, dịch văn bản Trung qua thủ công/Gemini/OpenAI, tạo giọng đọc qua ai33.pro.

**[Tải bản 0.8](https://github.com/tinhot24h/Dungx/raw/refs/heads/main/ReviewStudio-v0.8.zip)** · Cài/chạy: `HUONG_DAN.txt`.

## Mới trong 0.8

- Timeline chung với thước thời gian, ảnh nhỏ video và sóng âm MP3 tạo cục bộ. Zoom 1–12×, kéo đầu phát, tua từng khung hình; kéo mép để cắt hoặc kéo thân MP3 để đổi thời điểm vào. Sóng âm hiển thị tương đối theo track, không tự tăng âm lượng nguồn.
- Chọn track rồi dùng thanh tốc độ/âm lượng hoặc mở **Nhập số chính xác**. Hai nút cắt trước/sau đầu phát, bám mốc, hoàn tác/làm lại tối đa 60 bước chỉnh track. ←/→ từng khung hình, Shift = 10 khung; Space phát/dừng khi focus timeline. Mỗi track vẫn giữ một đoạn liên tục, chưa có tách/ghép nhiều đoạn.
- Chữ có **căn dọc trên/giữa/dưới trong hộp**. Đặt H lớn hơn chiều cao chữ để thấy khác biệt; H = 0 tự động vừa chữ. Tính toán dùng chung preview/MP4.
- Nhập API key xong: tự tải giọng và trang lịch sử hiện tại, không cần bấm tải. Lịch sử tự làm mới mỗi 30 giây khi tab Âm thanh ai33 đang hiển thị, sau tạo/lấy audio; vẫn có nút làm mới và phân trang. Thẻ tác vụ hoàn tất có **Lấy audio đã tạo**; chỉ truy vấn/cache tác vụ cũ, không gọi TTS mới. Không tải hàng loạt MP3 tự động.
- **Hủy xuất video** dừng tiến trình FFmpeg hoặc hủy lượt đang chờ; xóa file xuất dở, giữ nguồn/thiết kế. Chờ thông báo đã hủy rồi chỉnh và xuất lại. Nút này chỉ hủy dựng video cục bộ, không hủy tác vụ TTS ai33.

## Mới: Âm thanh ai33

Mở tab **Âm thanh ai33** hoặc bấm **Tạo giọng ai33** từ kịch bản tiếng Việt:

1. Nhập **ai33.pro API key** trong ứng dụng, hoặc đặt `REVIEW_AI33_KEY` / `AI33_API_KEY` trước khi chạy máy chủ. Không dùng key Gemini/OpenAI, không gửi key trong chat.
2. Lấy kịch bản từ tab AI hoặc dán văn bản Việt. Có thể lấy nội dung review hiện tại.
3. Chọn thư viện Edge/Vbee/ElevenLabs/Minimax/Kokoro/Fish Audio/giọng clone đã có; tự tải các trang của nhà cung cấp đã chọn; lọc ngôn ngữ, giới tính và tìm kiếm. Giới hạn mỗi đợt 100 trang/10.000 giọng, có thông báo khi chưa tải hết. Có thể nhập trực tiếp voice_id có prefix. Giọng ví dụ `edge_vi-VN-HoaiMyNeural` lấy từ tài liệu, quyền dùng giọng phụ thuộc tài khoản.
4. Chỉnh tốc độ **0,5–1,5**; có thể gửi tên file gợi ý hoặc ID từ điển phát âm đã tạo ở ai33.
5. Kiểm tra số dư credit nếu muốn, bấm **Tạo audio**. Tool gửi multipart/form-data tới API v3, giữ task_id và theo dõi qua Common API v1.
6. Khi `done`, lấy `metadata.audio_url`, tải/chuẩn hóa MP3 rồi nghe và tải trong tool. Nếu lỗi, dừng và hiển thị hướng dẫn; không tự tạo lại tác vụ.

Tạo giọng có thể trừ credit ai33, độc lập với chế độ dịch miễn API. Chi phí thực tế phụ thuộc provider/giọng/tài khoản; không tự ước tính cước. Poll mỗi 5 giây, dừng khi done/error hoặc sau 15 phút theo dõi. Dừng tự kiểm tra không hủy tác vụ ở ai33. Có thể kiểm tra task_id hoặc chọn lịch sử để lấy lại file mà không tạo lại.

MP3 đã lưu có nút **Dùng MP3 này trong video**; có thể chọn lại trong thư viện hoặc nhập MP3 thủ công. Nguồn TTS tối đa 1.000.000 ký tự theo tài liệu, file nguồn tải tối đa 100 MB; kịch bản rất dài nên chia đoạn. MP3 đã cache vẫn nghe/tải được khi tải lại trang; key cần nhập lại để truy vấn ai33. Khi đổi thư mục ứng dụng, file cache cũ không được chuyển tự động.

Key chỉ ở bộ nhớ phiên/server environment, không lưu file/localStorage/ZIP. Key không gửi tới CDN/media host. Link audio chỉ lấy từ tác vụ đã xác thực, không có endpoint nhận link tải tùy ý. File chuyển bằng FFmpeg có `libmp3lame`; MP3 hỗ trợ HTTP Range để tua/nghe trong trình duyệt. Định dạng nguồn hỗ trợ MP3/WAV/FLAC/Ogg/M4A, không nhận playlist.

Phạm vi hiện tại là TTS một giọng, thư viện giọng, credit và lịch sử. Chưa tạo clone mới, hội thoại nhiều người, CRUD từ điển, xóa/refund tác vụ, tải transcript. API contract và nguồn ảnh tài liệu: [docs/ai33-api.md](docs/ai33-api.md).

## Chọn cách dịch

| Chế độ | Cần key? | Cách hoạt động |
| --- | --- | --- |
| **Thủ công — mặc định** | Không | Tool ghép nguồn + phong cách thành câu lệnh. Bạn sao chép sang Gemini/ChatGPT web, lấy câu trả lời rồi dán trở lại. Tool không gọi API. Dịch vụ web có hạn mức riêng. |
| **Gemini API** | Key Google AI Studio | Dịch ngay trong tool. Có thể dùng hạn mức miễn phí nếu dự án/model/tài khoản đủ điều kiện; quota và cước do Google quyết định. Tool không thể khóa mọi lượt gọi ở mức miễn phí. |
| **OpenAI API** | Key OpenAI | Dịch ngay trong tool, phí API tính riêng với ChatGPT Free/Plus. |

Tool không tự chuyển provider, không tự thử lại hoặc dùng OpenAI trả phí khi Gemini hết quota. Bạn có thể chủ động đổi về Thủ công. Không tự điều khiển tài khoản web hoặc lấy cookie/token của ChatGPT/Gemini.

## Dùng không cần API

1. Mở **Dịch & biên tập AI**, chọn **Thủ công**.
2. Dán văn bản Trung (tối đa 8.000 ký tự), chọn Review/Tin tức/Mẹo/Giới thiệu, giọng văn, xưng hô và thời lượng.
3. Bấm **Tạo câu lệnh** rồi sao chép sang Gemini hoặc ChatGPT web. Link chỉ mở website để bạn tự thao tác.
4. AI được yêu cầu trả JSON gồm `literal`, `script`, `notes`. Sao chép đủ JSON vào ô kết quả thủ công, bấm nhập. Chấp nhận JSON được bọc trong khối markdown `json`.
5. Nếu chỉ có văn bản kịch bản, dán trực tiếp vào ô **Kịch bản tiếng Việt**; có thể điền bản dịch sát nghĩa riêng bằng tay.
6. Sửa, sao chép hoặc tải TXT UTF-8 để tạo MP3 bên ngoài. Bôi đen đoạn tối đa 600 ký tự để đưa lên khung nội dung video.

Tạo câu lệnh và nhập kết quả là xử lý cục bộ, không gọi OpenAI/Gemini API. AI web vẫn cần Internet và có giới hạn do nhà cung cấp áp dụng. Đây là quy trình thủ công, không phải bản dịch tự động chạy offline.

## Gemini API và OpenAI API

Chọn provider trong giao diện, nhập key ở **Kết nối API**. Key của từng provider giữ riêng trong bộ nhớ phiên; không lưu key trong localStorage, file hay ZIP. Tải lại trang cần nhập lại. Model được lưu riêng theo provider. Không gửi key trong chat.

- Gemini: lấy key tại https://aistudio.google.com/apikey. Model gợi ý `gemini-2.5-flash`, có thể thay bằng model tài khoản hỗ trợ. Kiểm tra điều kiện, hạn mức và giá hiện hành tại https://ai.google.dev/gemini-api/docs/pricing. Biến máy chủ: `REVIEW_GEMINI_KEY`, `GEMINI_API_KEY` hoặc `GOOGLE_API_KEY`; model mặc định tùy chọn `GEMINI_MODEL`.
- OpenAI: https://platform.openai.com/api-keys. Model mặc định `gpt-4.1-mini`, cần Responses API/Structured Outputs. Biến máy chủ: `REVIEW_OPENAI_KEY` hoặc `OPENAI_API_KEY`; model tùy chọn `OPENAI_MODEL`.

Chỉ khi bấm dịch trong chế độ API, văn bản/cấu hình gửi tới provider đã chọn. Gemini dùng HTTPS `generativelanguage.googleapis.com` với header `x-goog-api-key`, không đưa key lên URL; OpenAI dùng HTTPS `api.openai.com/v1/responses`, `store:false`. Không gửi clip/PNG tới các API dịch.

Nguồn hiện là văn bản dán vào. **Chưa có nhận lời nói từ video hoặc OCR. Phần dịch không tạo giọng; MP3 được tạo riêng trong tab Âm thanh ai33.** Bản dịch sát nghĩa, bản viết lại và ghi chú đều cần người dùng duyệt. Thời lượng 15/30/60/90 giây chỉ là mục tiêu; ước tính đọc 2,8 tiếng/giây. Không coi lời AI là xác minh giá, công dụng hay sự kiện.

## Dựng video

Giữ các chức năng 0.4: hệ tọa độ 720×1280 px, X/Y tính từ góc trái trên; W/H khung/video, cỡ chữ 12–144 px (nhập 90 px được), căn giữa hai trục; kéo trực tiếp bốn lớp. Video liên kết W/H 9:16 mặc định, có thể bỏ chọn để kéo giãn.

Nền một/chuyển hai màu và hòa nền alpha mềm; sáu khung dựng sẵn hoặc PNG từ máy (5 MB, 4096 px/cạnh, 8 triệu điểm ảnh; PNG động lấy hình đầu). Sáu font Sans/Serif/Mono thường/đậm kèm giấy phép. Tiêu đề/nội dung chỉnh độc lập màu/font/cỡ/vị trí/căn dòng/viền, không thêm CTA.

MP4 H.264/AAC: 720×1280, **1080×1920**, **2K 1440×2560**, **4K 2160×3840**; nén tiêu chuẩn/chất lượng cao. Nguồn tối đa **500 MB / 30 phút**. Khung/video có thể nằm ngoài canvas và bị cắt; chữ vượt cạnh phải/chiều cao báo lỗi. Baseline/viền chữ giữa trình duyệt và MP4 có thể chênh nhẹ. Không xóa chữ/watermark có sẵn trên nguồn.

## Quy trình dựng 0.7

1. **Chọn nguồn:** tải video, đặt tên dự án; nhập MP3 (100 MB) hoặc chọn audio ai33 đã lưu. Thư viện giữ tên, thời lượng và task_id để đối chiếu; tên gửi ai33 được dùng khi tải MP3. Tác vụ cũ thiếu tên từ API được nhận diện bằng task_id.
2. **Cắt & khớp âm thanh:** kéo hai đầu từng track hoặc nhập giây bắt đầu/kết thúc (cuối = 0 nghĩa toàn bộ). Mỗi nguồn giữ một đoạn liên tục; chưa cắt bỏ nhiều đoạn ở giữa. Tốc độ video/MP3 độc lập **0,25–4×**, MP3 giữ cao độ; âm lượng **0–300%**, trễ MP3 theo giây. Chọn giữ tiếng gốc, thay bằng MP3 hoặc trộn hai nguồn.
3. **Khớp thời lượng:** theo MP3 (giữ hình cuối nếu video thiếu); theo video (cắt/đệm im lặng MP3); hoặc lấy đoạn ngắn hơn. Hai nút khớp tốc độ hỗ trợ căn thời lượng; không tự căn từng câu nói.
4. **Thiết kế:** video có zoom **25–400%**, xoay **−180°…180°**, kiểu phủ kín/vừa khung/kéo giãn. Bấm chữ để chọn, nhấp đúp để sửa trực tiếp; Ctrl+Enter xác nhận, Escape hủy. Kéo hộp để di chuyển, kéo góc dưới phải để đổi kích thước chữ/khung/video. Hộp chữ có W/H; **H = 0 tự động**. Chữ tràn được cảnh báo viền đỏ và chặn xuất đến khi chỉnh vừa. Căn trái/giữa/phải/đều hai bên; dòng cuối đoạn căn trái khi căn đều.
5. **Xuất video:** chọn độ phân giải và chất lượng. Tọa độ thiết kế luôn 720×1280; video và chữ dựng theo kích thước xuất. Nguồn thấp không có thêm chi tiết khi xuất 4K. Khung PNG trang trí được phóng theo tỷ lệ.

Xem trước phát hai track theo cắt/tốc độ/trễ đã chọn; duyệt lại MP4 sau xuất. Chưa ghép nhiều clip, nhiều MP3 hoặc tạo phụ đề theo câu.

Nếu ai33 đã tạo xong nhưng tool không tải được: chọn đúng task_id/lịch sử và bấm **Kiểm tra tiến độ** để lấy link mới. Lỗi mới có mã HTTP/mạng/TLS/định dạng để chẩn đoán. Nút **Mở audio gốc bằng trình duyệt** cho phép lưu rồi nhập MP3 thủ công; không bấm Tạo audio lại. Chưa xác minh tải từ CDN thật của tài khoản bạn vì môi trường kiểm thử không có key và không truy cập được host ai33.

## Đề xuất nâng cấp tiếp theo (chưa triển khai)

1. **Ưu tiên cao:** tách một clip thành nhiều đoạn, xóa phần giữa và đóng khoảng trống; nhiều MP3/video trên timeline. Hiện chỉ giữ một đoạn liên tục mỗi track.
2. **Cắt tiếng thừa:** đánh dấu khoảng lặng theo ngưỡng và nghe thử trước khi cắt; fade in/out, crossfade, đo âm lượng để ghép lời đọc mượt hơn.
3. **Lưu dự án đầy đủ:** mở lại timeline/thiết kế/nguồn, đóng gói dự án chuyển máy; thêm preset mẫu review/tin tức theo sản phẩm.
4. **Phụ đề:** nhập SRT Việt, chỉnh thời điểm và tô sáng từ đang đọc; nhận dạng giọng nói là bước riêng, cần chọn máy cục bộ hoặc API.
5. **Xuất nhiều video:** hàng đợi có tiến độ từng clip, hủy từng lượt, preset chất lượng và tùy chọn GPU khi máy hỗ trợ.

## Chạy và cập nhật

Cần Python 3.11+, FFmpeg/FFprobe với libx264/drawtext, libmp3lame cho MP3. Không cài pip/npm/SDK dịch vụ. Python/FFmpeg không kèm ZIP; chưa phải EXE.

```sh
python3 launch.py
```

Windows mở `START_WINDOWS.bat`; macOS/Linux chạy lệnh trong thư mục giải nén. Cổng loopback mặc định 8000; đặt `PORT` để đổi, `--no-browser` không tự mở trình duyệt. Health: `curl --fail http://127.0.0.1:8000/health`.

Dừng bản cũ, giải nén thư mục mới rồi chạy; không cần cài lại Python/FFmpeg. Thiết kế px 0.4 được giữ cùng khóa trình duyệt. Nếu cùng trình duyệt/địa chỉ/cổng và chưa có thiết kế px, có thể chuyển bản lưu 0.3 từ % sang px. PNG ở thư mục cũ cần tải lại.

## Dữ liệu và giới hạn

Thiết kế và văn bản AI lưu riêng trong localStorage; có nút xóa văn bản. Key không lưu kèm. Video/PNG/MP4/MP3 trong `.local/`, Git và gói ZIP bỏ qua. Trạng thái xuất video ở RAM, mất khi dừng máy chủ: tải kết quả trước khi dừng. Chỉ xóa `.local/` khi ứng dụng đã dừng và đã giữ tệp cần thiết.

Chỉ dùng cục bộ với Host/Origin localhost; chưa có xác thực, dọn ổ đĩa, giới hạn hàng đợi video hoặc triển khai công khai. Chưa ghép nhiều clip hay đăng TikTok tự động.

## Kiểm chứng

0.8: 44 kiểm thử Python; FFmpeg thật tạo ảnh nhỏ/sóng âm, xuất và hủy rồi xuất lại. Chromium kiểm tra timeline chung, kéo MP3, thanh tốc độ, undo/redo, zoom, căn dọc, tự tải giọng/lịch sử với phản hồi API giả lập, xóa key và bố cục 320/390px. Chưa thử trực tiếp Windows/macOS hoặc AI33 thật.

AI33: kiểm tra HTTP giả lập đúng API v3/v1 do người dùng cung cấp; key/header/multipart, phân trang giọng, trạng thái doing/done/error, credit/history, không retry tạo, không lộ key. FFmpeg đã chuyển WAV mẫu thành MP3 thật, FFprobe xác minh, Chromium phát/tua/download MP3 qua Range 206/416, khôi phục cache sau reload và không lưu key; bố cục 390/320px. Chưa gọi ai33 thật vì không có key và mạng môi trường chặn host; cần thử synthesis thực với tài khoản có quyền/credit.

Đã kiểm tra luồng thủ công thực qua HTTP và Chromium: không cần key, không gọi API, tạo/sao chép câu lệnh, nhập JSON thường/có code fence, từ chối JSON sai mà giữ bản cũ, xuất TXT. Gemini/OpenAI được kiểm tra bằng HTTP giả lập: định dạng request, provider/key tách biệt, hết quota không fallback/không retry, không lộ key trong URL/prompt/localStorage. Chưa gọi hai API thật vì máy kiểm tra không có key; chưa xác minh tài khoản/model cụ thể được miễn phí. Chưa chạy trực tiếp Windows/macOS.

```sh
python3 -m unittest discover -s tests -v
node --check studio.js
node --check ai_ui.js
node --check audio_ui.js
node --check editor_ui.js
node --check timeline_ui.js
python3 build_package.py
```

API thêm: `POST /translation-prompt` (source + phong cách → prompt, không gọi API), `POST /translation-import` (text JSON → hai bản + ghi chú), `/ai-status` trả cấu hình an toàn theo provider. `/translate` nhận thêm `provider: gemini|openai`; giá trị `manual` bị từ chối tại endpoint dịch để không vô tình gọi API.

API cục bộ ai33: `GET /audio-config`, `POST /audio/voices`, `/audio/create`, `/audio/task`, `/audio/credits`, `/audio/history`, `/audio/cache`; `POST /audio/upload`, `GET /audio/assets`, `GET /audio/file/<asset-id>` để phát hoặc `?download=1` để tải. Không nhét API key vào query string.
