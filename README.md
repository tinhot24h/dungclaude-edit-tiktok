# Review Studio 0.17.2

Dựng video review 9:16, dịch văn bản Trung qua thủ công/Gemini/OpenAI, tạo giọng đọc qua ai33.pro.

**Tải bản đóng gói:** mục [Releases](https://github.com/tinhot24h/dungclaude-edit-tiktok/releases) (tạo bằng `python build_package.py`; file ZIP không còn commit vào repo) · Cài/chạy: `HUONG_DAN.txt`.

## Mới trong 0.17.2

- **Bỏ chèn phụ đề lên video** ở tab Lồng tiếng: video xuất ra không còn chữ phụ đề trên hình. Vẫn có thể chọn file .srt đi kèm, kênh phụ đề trong MP4 (bật/tắt được trong trình phát) hoặc không phụ đề. Cấu hình cũ đang chọn "Chèn chữ lên video" tự chuyển sang file .srt đi kèm.

## Mới trong 0.17.1

- **Overlay không bắt buộc:** mặc định tắt. Thêm file overlay vào thư viện không tự bật; nếu bật mà chưa có/chưa chọn overlay nào, video vẫn xuất bình thường (không có overlay) kèm cảnh báo, không bị dừng.
- **Overlay tự khớp thời lượng video:** overlay dài hơn video thì tự cắt bằng video; ngắn hơn thì chọn:
  - *Suốt video · lặp 1 overlay, cắt khớp* — lặp lại một overlay rồi cắt đúng độ dài.
  - *Suốt video · ghép nối nhiều overlay ngẫu nhiên* — nối nhiều overlay khác nhau (không trùng liền nhau) cho đến khi phủ hết video rồi cắt khớp.
  - *Một đoạn ngẫu nhiên* — chèn overlay ở một vị trí ngẫu nhiên.

## Mới trong 0.17

- **Tab Lồng tiếng thiết kế lại cho gọn, dễ dùng:**
  - **Thanh trên cùng** (luôn hiện khi cuộn): chọn/lưu/xóa **cấu hình lồng tiếng**, trạng thái key (bấm vào để mở mục Kết nối) và nút **▶ Lồng tiếng N video**.
  - **Cột trái** chia mục theo thứ tự làm việc: 🎬 Video đầu vào → 🔑 Kết nối → ✂ Cắt & khung hình → ✨ Overlay → 🗣 Nhận diện & dịch → 🎙 Giọng đọc → 🎵 Âm thanh gốc → 📤 Xuất & phụ đề. Mỗi lần chỉ mở một mục; tiêu đề mỗi mục hiện tóm tắt thông số đang chọn.
  - **Cột phải** là **khung xem trước** video đầu tiên và **hàng đợi gọn**. Khung xem trước có khung hình, nền mờ, xoay/lật/zoom, overlay mẫu và nút phát.
- **Xử lý hàng loạt không rối:**
  - Mỗi video là một dòng trong hàng đợi: trạng thái, 5 bước, tiến độ, nút chính. Bấm vào dòng để xem chi tiết và các nút khác.
  - Lọc theo Tất cả / Đang chạy / Cần xử lý / Xong.
  - Nút hàng loạt: **Chạy lại lỗi**, **Dừng tất cả**, **Xóa đã xong**.
  - Video lỗi (ví dụ không có tiếng) không làm dừng các video khác.
- **Cắt đầu / cắt cuối video:** ví dụ bỏ 0,5s đầu và 0,5s cuối. Áp dụng cho mọi video trong lô, cắt chính xác trước khi nhận diện.
- **Khung hình video khi lồng tiếng:**
  - Khung xuất: giữ gốc / 9:16 / 4:5 / 1:1 / 16:9.
  - Cách đặt: lấp đầy, giữ toàn bộ (viền đen), giữ toàn bộ trên nền mờ.
  - Zoom 25–300%, dịch ngang/dọc, xoay, nút ↺90° ↻90°, lật ngang/dọc, đặt lại.
  - Bản xuất giống khung xem trước.
- **Overlay ngẫu nhiên:**
  - Thêm file hoặc cả thư mục overlay (video hiệu ứng, GIF, PNG/JPG), hoặc kéo thả vào mục ✨.
  - Tích chọn overlay nào được dùng; mỗi video lấy ngẫu nhiên 1–3 overlay.
  - Hòa trộn: **Sáng** (hiệu ứng nền đen như ánh sáng, bụi lấp lánh), **Bình thường** theo độ đục, hoặc **Tách nền xanh**.
  - Thời gian: lặp suốt video hoặc một đoạn ngẫu nhiên. Phụ đề luôn nằm trên overlay.
- **Cấu hình lồng tiếng đã lưu:** lưu toàn bộ thông số bên trái (giọng, văn phong, khung hình, overlay, phụ đề…) để chạy các lô sau giống hệt.

## Mới trong 0.16.2

- **ai33 chỉ tạo MP3:** khi lồng tiếng, ứng dụng không còn yêu cầu ai33 tạo SRT/JSON phụ đề, tránh làm lỗi tác vụ.
  - Phụ đề tiếng Việt do ứng dụng tự tính: chia đoạn văn thành câu theo độ dài, rồi đặt điểm chuyển câu vào khoảng lặng gần nhất trong file giọng, để chữ đổi đúng lúc giọng ngắt nghỉ.
- **Bỏ khu bản dịch khỏi hàng đợi:** mặc định chỉ còn danh sách tác vụ. Khi cần sửa câu, bấm **✎ Bản dịch** trên tác vụ để mở, bấm **✕ Đóng bản dịch** để ẩn.

## Mới trong 0.16.1

- **Sửa lỗi "ai33 đã tạo MP3 nhưng ứng dụng không tự lấy về":**
  - Hỏi trạng thái ai33 gặp lỗi tạm thời (HTTP 5xx, mất mạng, quá nhiều yêu cầu) thì ứng dụng chờ rồi hỏi lại, tối đa khoảng 10 phút, thay vì dừng ngay. Thông báo hiện số lần thử và mã lỗi HTTP.
  - Nếu cách hỏi theo mã tác vụ không được, ứng dụng tìm tác vụ trong lịch sử ai33 để lấy link MP3.
  - Chỉ dừng ngay khi key sai, hết credit hoặc bị từ chối quyền.
  - Thêm nút **⬆ Dùng MP3 đã tạo** trên tác vụ bị lỗi hoặc đang dừng: tải file MP3 lấy từ lịch sử ai33 lên, ứng dụng căn giọng và xuất video luôn, không tạo giọng lại.

## Mới trong 0.16

- **Lồng tiếng thành 1 file giọng (mặc định):** dịch toàn bộ lời Trung thành **một đoạn văn tiếng Việt liền mạch**, gửi ai33 **một tác vụ**, nhận **một file giọng**.
  - Muốn khớp khẩu hình hơn thì chọn chế độ cũ "Từng câu theo thời gian".
- **Khớp thời lượng giọng ↔ video** (bước 04):
  - Giữ tốc độ giọng, chỉ đọc nhanh khi giọng dài hơn video.
  - **MP3 khớp video:** co giãn giọng (0,8× đến mức tối đa) để kết thúc cùng video.
  - **Video khớp MP3:** tua nhanh hoặc làm chậm video (0,25–4×), nhạc nền đổi tốc độ theo.
- **Chọn giọng ai33 ngay trên trang Lồng tiếng:** nút 🎙 Chọn giọng ai33 mở danh sách giọng (Edge, ElevenLabs, MiniMax, Vbee, Fish Audio, Kokoro, giọng clone), có tìm kiếm và lọc nam/nữ. Bấm ▶ nghe thử, bấm Chọn để dùng.
- **Chạy tự động 1 bước:** bấm "Bắt đầu" là chạy hết từ nhận diện tới video xuất, không dừng giữa chừng để hỏi. Ô "Dừng sau bước dịch để tự duyệt câu" vẫn còn nếu bạn cần.
- **Xem trước video đầu tiên:** trên hàng đợi hiện video đầu tiên đã chọn. Âm nền nghe như sau khi xử lý.
- **Khu duyệt câu dịch:** thanh tiêu đề luôn hiện trên cùng khi cuộn, gồm trạng thái, các bước và nút Tiếp tục / Dừng / Tải MP4. Ở chế độ đoạn văn: lời Trung bên trái, đoạn văn Việt sửa được bên phải (đếm số tiếng/giới hạn), phụ đề theo giọng bấm vào để tua.
- **Mẫu văn phong dịch** (dùng chung trang Dịch AI và Lồng tiếng): Review sản phẩm, Gia dụng · nhà cửa, Trải nghiệm thực tế, Tin tức · thời sự, Chia sẻ mẹo, Giới thiệu sản phẩm, Làm đẹp · chăm sóc, Công nghệ · điện tử, Ẩm thực, Thời trang, Giải trí · hài hước. Mỗi mẫu có cách mở đầu (hook) riêng.
- **Luôn áp dụng, không tắt được:** không nhắc giá, thương hiệu, khối lượng, kích thước, thể tích, công suất chính xác; chỉ dùng từ ngữ chung chung.

## Mới trong 0.15

- **Lưu API key:** bên dưới mỗi ô key (OpenAI, Gemini, ai33) có nút **💾 Lưu key trên máy này**, nên lần sau không phải nhập lại.
  - Không bấm lưu thì key chỉ giữ trong phiên như trước.
  - Key được lưu trong `.local/secrets.json` trên máy bạn, không nằm trong ZIP hay bản cập nhật. Giao diện chỉ hiện 4 ký tự cuối.
  - Có nút **Xóa key đã lưu**. Người dùng chung máy hoặc chung tài khoản Windows cũng dùng được key đã lưu.
- **Câu lệnh dịch dùng chung:** trang Lồng tiếng dùng luôn mẫu câu lệnh đã sửa ở trang Dịch & biên tập AI (phần quy tắc nội dung và văn phong).
  - Quy tắc cố định cho mọi mẫu: tuyệt đối không nêu giá, tên thương hiệu, tên shop, mã model, kích thước, thể tích, dung tích, khối lượng, công suất chính xác; chỉ dùng từ chung chung ("giá mềm", "nhỏ gọn", "dung tích lớn"…).
  - Câu có con số kèm cm, ml, lít, kg, W, mAh… sẽ hiện cảnh báo.
- **Chỉnh video gốc** (tab Khung hình):
  - Căn trái/giữa/phải, trên/giữa/dưới, đặt giữa khung.
  - Kích thước nhanh: Lấp đầy 9:16, Giữ toàn bộ hình, Vừa chiều ngang/dọc theo đúng tỷ lệ video gốc.
  - Zoom 100–200%, thanh xoay kèm nút ↺90° ↻90° 180° 0°, **lật ngang/lật dọc**. Bản xuất giống bản xem trước.
- **MP3:** bảng Giọng đọc và Nhạc nền có thanh và nút nhanh cho tốc độ (0.75×–1.5×) và âm lượng (Tắt/50/100/150/200%). Nhạc nền có thêm tốc độ riêng.
- **Tự khớp thời lượng** (bảng Giọng đọc): "MP3 khớp video" hoặc "Video khớp MP3". Ứng dụng tự đổi tốc độ sau mỗi lần cắt/sửa để hai track kết thúc cùng lúc.
- **Mục Xuất sắp xếp theo thứ tự:** ① Thông số xuất → ② Cấu hình đã lưu → ③ Xuất video đang dựng → ④ Xuất hàng loạt.
  - **Cấu hình đã lưu:** lưu cả thiết kế, âm thanh, tốc độ, tự khớp, nhạc nền và độ phân giải để dùng lại.
  - **Xuất hàng loạt:** tích nhiều video trong kho. Chọn MP3 (tự tìm MP3 cùng tên / không dùng / dùng MP3 đang chọn) và chữ (giữ chữ / tiêu đề = tên video / không chữ). Mỗi video xuất đủ độ dài với cùng thông số, tự khớp MP3 nếu bật, có tiến độ từng video và nút Dừng tất cả.

## Mới trong 0.14

- **Trang Lồng tiếng (mới):** tự động lồng tiếng video tiếng Trung sang tiếng Việt theo 5 bước:
  1. **Nhận diện:** OpenAI Whisper nhận lời nói, xuất SRT tiếng Trung có thời gian (khoảng 0,006 USD/phút). Có sẵn file .srt cùng tên thì bỏ qua bước này.
  2. **Dịch OpenAI:** dịch tự nhiên, mỗi câu giới hạn số tiếng theo thời gian nói (mặc định 4,2 tiếng/giây), không đọc giá chính xác, có ghi chú văn phong và cách xưng hô.
  3. **Tách âm thanh gốc:** giảm tiếng gốc khi có lời (giữ nhạc nền), lọc giọng giữa (thử nghiệm), tách giọng AI bằng Demucs nếu đã cài (`pip install demucs`), giữ nguyên hoặc xóa hẳn tiếng gốc.
  4. **Lồng tiếng ai33:** gộp câu thành đoạn tự nhiên, tạo giọng Việt, tự đọc nhanh hơn (tối đa 1,3×) cho vừa chỗ trống rồi đặt đúng thời điểm.
  5. **Xuất:** MP4 H.264 + AAC, phụ đề Việt dạng file .srt, kênh phụ đề trong MP4 (không chèn chữ lên hình); tự lưu vào thư mục xuất.
- Chọn 1 video, nhiều video hoặc cả thư mục (kéo thả được), hoặc lấy từ kho Media; các video chạy lần lượt trong hàng đợi.
- Mặc định **dừng sau bước dịch để duyệt**: bảng câu Trung ↔ Việt có đếm số tiếng/giới hạn (đỏ khi quá dài), sửa xong bấm Tiếp tục. Sửa câu sau khi đã xong thì chỉ câu đó được tạo giọng lại.
- Tiến độ và mã tác vụ ai33 được lưu lại: dừng giữa chừng hoặc tắt ứng dụng thì bấm **Tiếp tục**, không tạo trùng giọng (không mất credit hai lần). Key API chỉ giữ trong phiên.
- **Mở trong trình dựng:** đưa video (chỉ còn nhạc nền) và giọng Việt sang trang Dựng video để thêm chữ, logo, khung rồi xuất như bình thường.
- **Giao diện trang dựng mới (tham khảo TaoClip):**
  - Thanh công cụ dọc bên trái: Media · Âm thanh · Văn bản · Ảnh/Logo · Xuất.
  - Kho media có nút "＋ Nhập media" / "＋ Nhập ảnh", mỗi thẻ có nút "Thêm vào timeline".
  - Bảng thuộc tính theo ngữ cảnh: chỉ hiện các tab của lớp đang chọn, kèm tên lớp và nút "Thiết kế chung". Clip video có tab Cắt & tốc độ (nút 0.5× 1× 1.5× 2× 4×, hiện độ dài) và tab Khung hình.
  - Trình phát có nút phát lặp ⟲ và thanh âm lượng xem trước.
  - Timeline có nút chữ "✂ Tách", "Snap: bật/tắt", "Vừa khung", mã track V1/A1/A2; nút ↶ ↷ trên thanh dự án.

## Mới trong 0.13

- **Cập nhật không cần tải lại toàn bộ:** nút **⟳** ở góc phải trên cùng tự kiểm tra GitHub khi mở ứng dụng; có bản mới thì hiện **⬆ Có bản …**. Bấm **Cập nhật ngay**: ứng dụng chỉ tải các file đã thay đổi, kiểm tra mã SHA-256 từng file, sao lưu bản cũ vào `.local/update`, rồi bấm **Khởi động lại** là dùng được bản mới. Video, MP3, dự án, kiểu chữ và cài đặt trong `.local` được giữ nguyên.
- Cập nhật ngoài ứng dụng: bấm đúp `UPDATE_WINDOWS.bat` (Windows) hoặc `UPDATE_MAC_LINUX.command`, hoặc chạy `python update.py` (`--check` để chỉ xem thay đổi). Thư mục là bản `git clone` thì dùng `git pull`.
- Từ 0.13 trở đi mới cập nhật được kiểu này: bản 0.12.1 trở về trước cần tải ZIP 0.13 một lần.

## Mới trong 0.12.1

- Bỏ mục tìm nhạc miễn phí (Openverse). Nhạc nền tải thủ công (ví dụ từ Thư viện âm thanh YouTube) rồi nhập vào kho Media như MP3 thường.

## Mới trong 0.12

- **Lớp ảnh / logo / sticker:** nhập PNG, JPG, WebP hoặc GIF vào kho Media (lọc "Ảnh & logo"), bấm ＋ hoặc kéo thẻ thả lên khung hình. Trên khung hình: kéo để di chuyển, kéo ô vuông ở góc/cạnh để đổi cỡ (giữ tỷ lệ), kéo nút tròn để xoay. Tab **Ảnh** có X/Y/W/H, góc xoay, độ đục, thời gian hiện, căn lề, "Góc logo", lên trên/xuống dưới, nhân bản, xóa. Mỗi ảnh có một thanh trên timeline để đổi thời gian hiện; Delete để xóa. Nút ▭ trên thẻ ảnh dùng ảnh đó làm khung PNG.
- **Tốc độ riêng từng đoạn video:** tách đoạn (S), bấm một đoạn (Shift+bấm để chọn nhiều), chỉnh ở bảng Clip video → "Tốc độ đoạn đang chọn" (0,25×–4×, nút 0.5×…3×, "Áp dụng cho mọi đoạn"). Tiếng gốc đổi tốc độ theo, giữ cao độ; đoạn có tốc độ khác hiện nhãn "2×" trên timeline.
- **Theo dõi tiến độ xuất:** thẻ tiến độ trong mục Xuất, thông báo nổi góc dưới phải (phần trăm, thời gian còn lại, nút Hủy), nút "Xuất bản" và tiêu đề tab trình duyệt hiện %. Xuất xong có âm báo, thông báo "Video đã xuất xong" với nút Mở thư mục / Tải về, và thông báo hệ thống nếu đang ở cửa sổ khác.
- **Thông số xuất gọn:** bấm ô "1080 × 1920 · 30 FPS" ở góc phải trên cùng (hoặc ô tóm tắt trong mục Xuất) để chỉnh độ phân giải, FPS, chất lượng, bộ mã hóa, âm lượng tổng và thư mục lưu trong một bảng nhỏ.
- **Bỏ "Xuất thử 5 giây"** (và phím P).
- **Sửa chữ trong tab Tiêu đề / Nội dung:** ô nhập nội dung nằm ngay đầu tab (kèm đếm ký tự). Mục Chữ bên trái liệt kê các lớp chữ, bấm để mở. Kéo chữ trực tiếp trên khung hình (có viền gợi ý khi rê chuột), nhấp đúp để sửa tại chỗ.
- **Kiểu chữ của tôi:** trong mỗi tab chữ, "Lưu kiểu này" lưu font, cỡ, màu, căn lề, viền, nền hộp, độ rộng; áp dụng cho bất kỳ lớp chữ nào.
- **Thiết kế của tôi:** ở cuối bảng thuộc tính, lưu/áp dụng/xóa cả thiết kế (nền, khung, kiểu chữ, vị trí, lớp ảnh/logo), không kèm nội dung chữ hay video/MP3.
- **Trang Dịch:** "Tạo câu lệnh" xóa kết quả cũ; "Nhập kết quả" thay toàn bộ kịch bản, hook, tiêu đề, nội dung theo câu trả lời mới. Nhập được cả câu trả lời có chữ giải thích hoặc ```json bao quanh, xuống dòng trong chuỗi, dấu ngoặc kép cong, dấu phẩy thừa.

## Mới trong 0.11

- **Kho media kiểu CapCut** (tab Media): ＋ Nhập nhiều file có thanh tiến độ, tìm kiếm, lọc Tất cả/Video/Âm thanh/Khung PNG; thẻ có ảnh nhỏ, sóng âm, thời lượng, nhãn "Đã thêm / Giọng đọc / Nhạc nền"; nút ＋ (♪ cho nhạc nền) và 🗑 xóa.
- **Kéo thả vào timeline:** kéo thẻ trong kho hoặc file từ thư mục máy tính thả thẳng vào track video, giọng đọc hoặc nhạc nền.
- **Lớp chữ trên timeline:** Tiêu đề, Nội dung và tối đa 6 lớp chữ thêm, mỗi lớp là một thanh màu cam: kéo thân để dời, kéo mép để đổi thời gian hiện, bấm để chỉnh thuộc tính, Delete để xóa. Phím **T** / nút **T+** / **＋ Thêm chữ** thêm chữ tại đầu phát.
- **Nền hộp cho chữ:** mỗi lớp chữ có thể bật hộp nền (màu, độ đục, khoảng đệm, bo góc); bản xuất giống hệt bản xem trước.
- **Kiểu nền "Tắt":** không dùng lớp màu/hòa nền.
- Gọn giao diện: cột trái còn Media · Âm thanh · Chữ · Xuất; bỏ các ô "Mẫu theo loại video".

## Mới trong 0.10.1 — trang Dịch & biên tập

- **Tùy chỉnh câu lệnh dịch:** mục ⚙ Tùy chỉnh câu lệnh cho sửa toàn bộ quy tắc viết gửi cho AI, lưu thành nhiều mẫu, chọn mẫu, khôi phục mặc định; tự lưu trên trình duyệt và dùng cho cả chế độ thủ công lẫn Gemini/OpenAI. Phần cảnh báo chống chèn lệnh và định dạng JSON luôn được ứng dụng tự thêm.
- **Quy tắc giá:** câu lệnh mẫu yêu cầu tuyệt đối không nêu giá bán chính xác, chỉ dùng cách nói chung chung ("giá mềm", "đang có ưu đãi"…). Kết quả có nêu giá cụ thể (vd 39 tệ, 99k, 150.000đ) sẽ hiện cảnh báo.
- Bỏ **bản dịch sát nghĩa** và **Điểm cần kiểm chứng**; AI chỉ trả hook, kịch bản đọc, tiêu đề và nội dung trên video. JSON kiểu cũ vẫn nhập được.
- **Giao diện mới:** bên trái là ô tiếng Trung lớn, tùy chọn gọn một hàng, nút chọn Thủ công / Gemini / OpenAI, các bước thủ công đánh số; bên phải là kết quả theo thứ tự ① Hook → ② Kịch bản đọc → ③ Chữ trên video, nút Tạo giọng ai33 ngay cạnh kịch bản.

## Mới trong 0.10 — giao diện dựng kiểu trình edit chuyên nghiệp

- **Thanh dự án:** đổi tên dự án ngay trên thanh, Tạo mới / Lưu, trạng thái lưu, thống kê (số track, đoạn, thời lượng), nút ẩn/hiện cột công cụ ◧, cột thuộc tính ▥, chế độ trình phát lớn ⛶, phím tắt ⌨ và nút **Xuất bản**.
- **Cột công cụ theo nhóm:** Media · Âm thanh · Chữ · Xuất · Thư viện · Dự án · Góp ý. Kéo vạch ngăn trên timeline để đổi chiều cao (nhấp đúp để đặt lại); bố cục được nhớ.
- **Timeline:** đầu track có tên, thông tin, nút tắt tiếng 🔊/🔇 (áp dụng cả khi xuất) và khóa 🔓/🔒; thanh công cụ icon (hoàn tác, tách, cắt trước/sau, xóa, mốc, nam châm bám mốc, zoom, mở rộng); đoạn có nhãn 01, 02…; Shift + bấm để chọn nhiều đoạn rồi xóa.
- **Phím Delete** xóa thứ đang chọn trên timeline: đoạn video, cả video MP4, MP3 giọng đọc hoặc nhạc nền (Ctrl+Z lấy lại). **Space** luôn phát/dừng, kể cả khi vừa bấm một nút.
- **Thanh phát:** timecode tới khung hình (phút:giây:khung), nhảy về/tới điểm cắt hoặc mốc, lùi/tới 1 giây, đồng hồ mức âm lượng khi phát, **Đo bản xuất** / **Đo giọng** (LUFS, True Peak theo EBU R128, nhắc mức TikTok ≈ −14 LUFS).
- **Góp ý (phím C):** bấm lên khung hình để ghim ghi chú đúng thời điểm và vị trí; danh sách lọc Mở / Đang sửa / Xong, cờ trên timeline, ghim số trên trình phát; lưu cùng dự án và hoàn tác được.
- Nhãn đoạn đang phát hiện ở góc trình phát.

## Mới trong 0.9.2

- **Trang Âm thanh ai33 làm lại:** ô soạn văn bản lớn bên trái (đếm ký tự, ước tính thời lượng, Ctrl+Enter để tạo); cột phải có tab **Cài đặt** và **Lịch sử**.
  - Chọn giọng trong thư viện dạng danh sách: nghe thử từng giọng, lọc theo nhà cung cấp, ngôn ngữ, giới tính; vbee có vùng miền/thể loại/nguồn giọng, Fish Audio có sắp xếp.
  - **Hội thoại nhiều giọng** (A>, B>, C>…): mỗi người nói một giọng và tốc độ riêng, chỉnh khoảng nghỉ, nút chèn nhãn nhanh.
  - **Từ điển phát âm:** tạo/sửa/xóa, xem thử câu sẽ được đọc thế nào, chọn từ điển khi tạo audio.
  - **Giọng nhân bản:** tạo từ file mẫu ≤ 10 MB, xóa giọng nhân bản.
  - **Xuất kèm phụ đề .srt**, tự phát khi xong, số dư credit luôn hiển thị.
  - Lịch sử dạng thẻ: giờ tạo, trạng thái, đoạn chữ, trình phát, tải MP3/SRT, tín dụng đã dùng, Dùng làm giọng đọc / Làm nhạc nền, xóa bản đã tải về máy.
- **Khung PNG:** bấm trúng khung trên trình phát để chọn (không còn bị khóa vào lớp khác), kéo để di chuyển, 8 ô kéo ở góc/cạnh để đổi kích thước, giữ tỷ lệ PNG (mặc định bật, hoặc giữ Shift). Tab Khung có nút căn trái/giữa/phải/trên/giữa/dưới, Vừa chiều ngang, Phủ toàn khung, Tỷ lệ gốc PNG; khung có thể lớn tới 1440 × 2560 hoặc lệch ra ngoài khung hình.

## Mới trong 0.9.1

- Trình phát thành cột riêng bên phải, cao suốt màn hình; khung 9:16 tự co giãn theo chỗ trống.
- Bấm thanh video / MP3 / nhạc nền trên timeline để mở ngay bảng thông số của clip đó (tab Clip video, Giọng đọc, Nhạc nền ở cột Thuộc tính).
- Timeline thu nhỏ được dưới 100% để nhìn bao quát: nút − / + / Vừa khung, Ctrl + lăn chuột.
- **Cắt phía trước / Cắt phía sau** (Q / W) cho đoạn đang ở đầu phát; **kéo một đoạn để đổi thứ tự**; xuất video theo đúng thứ tự mới.
- Dịch AI tạo thêm **hook mở đầu** theo phong cách viết (1 hook chính + 3 phương án), kịch bản bắt đầu bằng hook, tiêu đề giật tít nhưng không bịa thông tin.

## Mới trong 0.9

- **Bố cục kiểu CapCut:** thư viện/nguồn bên trái, thuộc tính ở giữa, trình phát 9:16 bên phải (nút Xuất thử / Xuất ngay trên trình phát), timeline trải dài phía dưới. Cột trái có 3 tab: Nguồn & xuất · Thư viện · Dự án & mẫu.
- **Mẫu theo loại video:** Review sản phẩm, Tin tức, Thời sự nóng, Gia dụng, Mẹo hay, Làm đẹp, Dùng chung (thay cho Mẫu hồng/Mẫu xanh). Áp mẫu giữ nguyên chữ và video, Ctrl+Z để hoàn tác.
- **Timeline:** tách đoạn tại đầu phát (S), bấm đoạn rồi Delete để xóa và nối liền, mốc (M), track nhạc nền thứ 3 (lặp, fade vào/ra, tự giảm khi có giọng đọc), bám mép đoạn/mốc.
- **Hoàn tác/làm lại cho mọi thao tác** (thiết kế + timeline), phím tắt đầy đủ (bấm ? để xem), Alt + mũi tên nhích lớp, đường gióng khi kéo, lớp phủ vùng an toàn TikTok (G).
- **Dự án & mẫu của tôi:** lưu/mở dự án, tự lưu mỗi phút, tải/mở file `.json`; lưu thiết kế thành mẫu riêng.
- **Thư viện media** có ảnh nhỏ; kéo thả video/MP3/PNG/.json từ thư mục vào cửa sổ; **xuất hàng loạt** nhiều video với cùng thiết kế.
- **Xuất video:** chọn **thư mục lưu**, xuất xong tự chép video vào đó (không cần bấm tải về; trùng tên thêm (2), (3)…); xuất thử 5 giây (P); hiển thị thời gian còn lại và thông báo khi xong; 60 fps; chuẩn hóa âm lượng −14 LUFS; hiệu ứng phóng to/thu nhỏ từ từ; tự dùng card đồ họa (NVIDIA/Intel/AMD/Apple) nếu có, lỗi thì tự chuyển về CPU.
- **Dịch AI:** prompt và kết quả có thêm **tiêu đề** và **nội dung hiển thị trên video**, độ dài tính theo font/cỡ chữ/độ rộng hộp chữ hiện tại (cảnh báo nếu tràn); nút **Đưa tiêu đề + nội dung lên video**.

## Mới trong 0.8.1

- **Dọn bộ nhớ:** dòng **Bộ nhớ** dưới mục audio hiện số video và dung lượng. Nút **Dọn video cũ** xóa video nguồn/video đã xuất không dùng quá N ngày; khi khởi động, ứng dụng tự dọn video không dùng quá 30 ngày (`REVIEW_KEEP_DAYS`, đặt `0` để tắt). Thư viện MP3 không bao giờ bị tự xóa; nút **Xóa MP3 đã chọn** xóa từng file.
- Tải video lên bị đứt hoặc bị từ chối không còn để lại file dở trong `.local/`.
- Video đã xuất vẫn tải được sau khi khởi động lại ứng dụng (trạng thái lưu ở `job.json`).
- Sửa lỗi ghi log khi trình duyệt hủy tải MP4 giữa chừng; giới hạn 30 phút dùng chung một hằng số; phiên bản đọc từ file `VERSION`.
- CI GitHub Actions chạy toàn bộ kiểm thử với FFmpeg.

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

Chọn provider trong giao diện, nhập key ở **Kết nối API**. Key của từng provider giữ riêng trong bộ nhớ phiên; chỉ khi bấm "Lưu key trên máy này" key mới được ghi vào .local/secrets.json (không bao giờ vào localStorage, ZIP hay bản cập nhật). Model được lưu riêng theo provider. Không gửi key trong chat.

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

Thiết kế và văn bản AI lưu riêng trong localStorage; có nút xóa văn bản. Key không lưu kèm. Video/PNG/MP4/MP3 trong `.local/`, Git và gói ZIP bỏ qua. Trạng thái xuất video lưu ở `job.json` cạnh video, nên vẫn tải được sau khi khởi động lại. Chỉ xóa `.local/` khi ứng dụng đã dừng và đã giữ tệp cần thiết.

Chỉ dùng cục bộ với Host/Origin localhost; chưa có xác thực, giới hạn hàng đợi video hoặc triển khai công khai. Chưa ghép nhiều clip hay đăng TikTok tự động.

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

## Phát hành bản mới (cho người bảo trì)

1. Sửa code, tăng số trong `VERSION`, thêm mục "Mới trong …" ở đầu README.
2. Chạy `python build_package.py --manifest` để cập nhật `MANIFEST.json` (mã SHA-256 của từng file).
3. Chạy `python -m unittest discover -s tests` (test sẽ báo lỗi nếu quên bước 2), rồi commit và push lên nhánh `main`.
4. Người dùng bấm ⟳ trong ứng dụng hoặc chạy `UPDATE_WINDOWS.bat` để nhận bản mới.
