# Review Studio 0.43.0

Làm video review / lồng tiếng TikTok **hàng loạt** trên máy Windows: chọn nhiều MP4 tiếng Trung → OpenAI nhận diện lời, dịch, viết tiêu đề / nội dung / tên file → ai33.pro đọc giọng Việt → FFmpeg ghép nền, khung, chữ, overlay và xuất MP4 hoàn chỉnh vào thư mục của bạn.

**Tải bản đóng gói:** mục [Releases](https://github.com/tinhot24h/dungclaude-edit-tiktok/releases) · Cài và chạy: `HUONG_DAN.txt`.

## Mới trong 0.43.0 · Gemini bên cạnh OpenAI

- Chọn Gemini để dịch/biên tập, giữ OpenAI Whisper cho nhận diện lời và ai33.pro cho giọng đọc.
- Thêm quản lý Gemini key, danh sách model được kiểm tra qua API, fallback cùng provider và thống kê token Gemini.
- Dự án cũ vẫn dùng OpenAI. Chưa xác minh các tên model Gemini được yêu cầu; hãy làm mới danh sách bằng key của bạn.
- **Sau khi cập nhật:** đóng ứng dụng rồi mở lại `START_WINDOWS.bat` để cài SDK Gemini vào đúng Python. Cần Internet/PyPI khi cài lần đầu. Người chạy trực tiếp bằng Python: `python -m pip install -r requirements-gemini.txt`.
- Kiểm thử API dùng mock, chưa kiểm chứng Gemini thật hoặc GUI Windows. Hai lỗi FFmpeg baseline vẫn còn (FPS và blend); xem phần Gemini cuối tài liệu.

## Mới trong 0.42.0 · Văn phong & Mẫu

**Văn phong xem / sửa được**
- Nút **👁 Xem / sửa** cạnh ô Văn phong: mỗi văn phong là các mục hướng dẫn gửi AI (tên, mô tả ngắn, giọng văn, 3 giây đầu, trình tự ý, nên dùng, tránh, câu mở mẫu, kiểu tiêu đề ưu tiên), có đếm ký tự. Sửa rồi **Lưu**; văn phong có sẵn đã sửa hiện dấu ✎ và có **↺ Về mặc định**.
- **＋ Lưu thành văn phong mới**: nhân bản thành văn phong riêng (vd "Review bếp miền Tây"), hiện ở nhóm "Văn phong tự tạo"; xóa được.
- **Xem toàn bộ câu lệnh gửi AI** (dưới ô Văn phong): đúng nguyên văn phần hướng dẫn app gửi OpenAI cho thiết lập đang chọn (mẫu câu lệnh + văn phong + hào hứng + xưng hô + ghi chú + giới hạn + phần chữ trên khung), từng lần gọi, có nút Copy.
- Lưu trên máy (`.local/dub/styles.json`), không mất khi cập nhật. Mỗi video giữ văn phong nó đã dùng (xuất lại ra đúng như cũ); mẫu mang theo văn phong, áp dụng mẫu trên máy khác tự thêm văn phong đó.

**Mẫu làm lại**
- **Thanh mẫu**: `📁 Mẫu: Khung hồng ✓` hoặc `● đã sửa 3` (rê chuột để xem sửa ở phần nào) · **💾 Lưu** (ghi đè mẫu đang dùng) · **＋ Lưu mới** · **↺ Về mẫu** (bỏ thay đổi). Trùng tên thì hỏi trước khi ghi đè.
- **Mẫu theo phần**: khi lưu, chọn phần nào vào mẫu (Chế độ chạy, Giọng & dịch, Âm thanh gốc, Video, Nền & khung, Tiêu đề & nội dung, Overlay, Lớp ảnh, Nhạc nền, Phụ đề, Xuất & thông tin file). Áp dụng chỉ đổi đúng các phần đó, nên **ghép được nhiều mẫu** (mẫu khung + mẫu giọng…).
- **Kiểm tra trước khi áp dụng**: hiện phần nào đổi bao nhiêu thông số; báo overlay / ảnh / nhạc / khung PNG không còn trong thư viện, văn phong sẽ được thêm.
- **Không lưu thông số của máy**: bộ mã hóa, số video chạy cùng lúc, thư mục xuất, key luôn theo máy đang dùng.
- **Quản lý mẫu** (bấm vào tên mẫu): thẻ có **ảnh xem trước** nền + khung + chữ, các phần trong mẫu, mô tả, lần dùng cuối; **Áp dụng · Đổi tên · Nhân bản · ⭐ Mặc định khi mở app · Xóa**; ô tìm mẫu.
- Mẫu lưu trước 0.42 vẫn dùng được (coi như đủ mọi phần).

## Mới trong 0.41.1 · chi phí ai33 chuẩn

- **Giá ai33.pro: $5 / 1 triệu ký tự** (tính cả dấu cách, dấu câu). Bảng kiểm tra trước khi chạy giờ hiện ai33 bằng **$ và đ** (trước đây chỉ có số ký tự), cộng dòng **Tổng ước tính** = OpenAI + ai33.
- **Ước ký tự chính xác hơn:** đo trên văn review tiếng Việt được trung bình 4,3 ký tự / tiếng (cũ 3,6, ước thiếu ~17 %). Video đã có bản dịch (dùng lại kết quả cũ, chỉ cần tạo lại giọng) thì tính theo **đúng số ký tự của bản dịch**, ghi "theo đúng bản dịch đã có". Video dùng lại được cả giọng cũ thì ai33 = 0 đ.
- **ai33 tháng này:** app đếm số ký tự thật đã gửi ai33 (mỗi lần tạo giọng, cả "nghe thử"), hiện "ai33 tháng này $…" ở thanh tổng quan hàng đợi và ô key (rê chuột để xem số ký tự, số lần tạo giọng). Lưu trong `.local/dub/ai33_spend.json`.
- Số tiền nhỏ hơn $0.01 hiện 4 chữ số lẻ (không còn "$0.000").
- Chế độ "ai33 lồng tiếng theo timestamp" tính theo phút (bảng giá riêng của ai33), vẫn hiện số phút như cũ.

## Mới trong 0.41.0 · Chế độ chạy & Thử 5 giây

- **Chế độ chạy** (ô trên cùng cột trái, lưu cùng Mẫu):
  - 🎙 **Lồng tiếng**: như trước (OpenAI + ai33).
  - ✍ **Chỉ chữ AI**: chỉ gọi OpenAI để viết tiêu đề / nội dung (khi nguồn chữ là "AI viết"), không tạo giọng ai33.
  - 🎬 **Chỉ dựng**: **không gọi API nào ($0)**, không cần key. Dùng để test nền, khung, tiêu đề, nội dung, overlay, lớp ảnh, nhạc nền.
- Ở Chỉ dựng / Chỉ chữ AI: mục *Nhận diện, dịch & viết chữ* và *Giọng đọc ai33* mờ đi kèm lời giải thích; nút chạy ghi rõ "▶ Xuất 12 video · không gọi API"; bảng kiểm tra ghi "Chỉ dựng video · không gọi API nào · $0"; hàng đợi có nhãn 🎬 chỉ dựng / ✍ chỉ chữ AI.
- **Chữ khi không gọi AI:** video đã có chữ AI từ lần chạy trước thì dùng lại đúng chữ đó (kèm tên file, tiêu đề file, tags AI); chưa có thì tiêu đề = tên file, nội dung = chữ ở ô **Cố định** của Nội dung (bảng kiểm tra nhắc khi ô này trống).
- **Âm thanh khi không lồng tiếng:** theo mục 🎵 Âm thanh gốc (giữ, tách giọng AI, xóa…) + nhạc nền. **MP3 cùng tên video** (chọn bằng "📂 Thư mục trên máy") được ghép làm giọng đọc, hiện "🎵 MP3" ở danh sách và hàng đợi.
- **⚡ Thử 5 giây** (cạnh nút chạy): xuất 5 giây đầu của video đang xem trước, luôn không gọi API, chỉ giữ trong app (không lưu ra thư mục xuất), vài giây là xong, mở ▶ Xem ngay ở hàng đợi. Video vẫn còn trong danh sách để chạy cả lô sau.
- **Sửa lỗi:** thiếu key (hoặc chưa chọn giọng) khi bấm chạy trước đây vẫn tạo tác vụ nằm "Đang chờ lượt" mãi; giờ chỉ báo lỗi, không để lại tác vụ kẹt. Dòng ghi chú "chạy mấy video cùng lúc" không còn bị ghi lẫn. Thanh trên cùng không còn tràn ngang trên màn hẹp.
- Khi đang "Sửa & xuất lại", ô Chế độ chạy bị khóa (xuất lại giữ chế độ và giọng/chữ đã có của video).

## Mới trong 0.40.0 · rà soát toàn bộ

- **Tắt app sạch sẽ:** bấm ⏻ (hoặc khởi động lại sau cập nhật) giờ dừng luôn mọi FFmpeg / Demucs đang chạy. Trước đây trên Windows chúng vẫn chạy ngầm sau khi tắt (ăn CPU, giữ khóa file video). Trên Windows, app và mọi tiến trình con còn được gắn với cửa sổ đen: đóng cửa sổ, Ctrl+C hay app bị treo/crash cũng không để lại FFmpeg nào. Cửa sổ thư mục mở bằng nút "Mở thư mục" và trình duyệt không bị đóng theo.
- **Video đang lồng tiếng khi tắt app** không bị đánh dấu lỗi: mở lại app sẽ tự chạy tiếp từ bước đang dở.
- **Hàng đợi không còn có thể "đứng im":** một lỗi bất ngờ trong 1 video trước đây có thể làm dừng luồng xử lý (các video sau không chạy nữa) và để video đó kẹt mãi ở "đang chạy". Giờ video đó báo lỗi rõ ràng, hàng đợi chạy tiếp.
- **Lỗi máy chủ luôn có thông báo:** mọi lỗi bất ngờ (kể cả ổ đĩa đầy) trả về câu báo lỗi dễ hiểu thay vì "Không thể kết nối máy chủ".
- Đã cho robot bấm thử 145 nút trên cả 2 trang (mọi mục, có bật thiết kế / overlay / lớp ảnh): không lỗi JavaScript, không lỗi máy chủ, không trùng id; mọi đường dẫn giao diện gọi đều có trên máy chủ.

## Mới trong 0.39.0

- **Hàng đợi phân trang:** thanh trang ở đáy khung (‹ 1 2 3 … 14 ›), chọn **10 / 20 / 50 / 100 video mỗi trang** (nhớ lựa chọn), hiện "21–40 / 269". Đổi nhóm (Tất cả / Đang chạy / Cần xử lý / Xong), ô tìm hoặc bước thì về trang 1.
- **Khung hàng đợi không còn tràn màn hình:** khung tự cao vừa cửa sổ, danh sách video cuộn bên trong khung; phần đầu (tiến độ, nhóm, tìm, chọn nhiều) và thanh trang luôn hiện.

## Mới trong 0.38.0

- **Video overlay không còn chồng lên nhau:** mỗi lúc chỉ 1 overlay. Overlay ngắn hơn video thì **ghép nối thêm overlay ngẫu nhiên** phía sau cho đủ (không lặp lại, không chồng), dài hơn thì cắt bằng video. Bỏ ô "Số overlay mỗi video"; cài đặt cũ 2–3 overlay hoặc "lặp 1 overlay" được chuyển sang cách mới (vẫn chọn lại "lặp" được ở *Thời gian*).
- **Rà lại toàn bộ nút căn:**
  - Video (*Cắt & vị trí video*): căn đúng mép khi video khác tỷ lệ khung (vd 4:3, 16:9 vào 9:16), khi "Giữ toàn bộ" / "Nền mờ" và khi xoay bất kỳ góc nào. Video đang vừa khít khung thì báo cần đổi Tỷ lệ thay vì im lặng.
  - Video trong chế độ thiết kế: các nút Căn trái / phải / trên / dưới / giữa tính theo hình thật đang hiện (kể cả "Giữ toàn bộ hình" và xoay), trước đây video 16:9 bấm "Căn trên" không nhúc nhích.
  - Lớp ảnh và video overlay: lưới căn 9 điểm tính cả góc xoay.
  - Căn dọc Trên / Giữa / Dưới của chữ: khi Cao = 0 (hộp vừa khít chữ) nút mờ đi và bấm vào sẽ chỉ cách (nhập Cao, hoặc dùng ⤒ ở Căn khung) thay vì như bị hỏng.
  - Kết quả căn được làm tròn đúng từng px của video xuất.

## Mới trong 0.37.0

- **Vị trí X/Y tính bằng px, chỉ dịch chuyển:** ở *Cắt & vị trí video*, *Lớp ảnh* và *Video overlay*, ô X / Y giờ là ô số có đuôi **px** (giống Biến đổi của tiêu đề / nội dung), tính theo pixel của video xuất (vd 1080×1920). 0 = chính giữa, số âm = sang trái / lên trên. Trong ô: ↑/↓ = 1 px, Shift + ↑/↓ = 10 px.
- **Vị trí không còn kiêm zoom:** trước đây đổi X/Y của video thì app tự phóng to video để che viền đen, nên trông như bị zoom. Giờ X/Y chỉ dời video theo trục đúng số px; phần lộ ra ở mép là nền (đen hoặc nền mờ). Muốn phủ kín thì tăng **Tỷ lệ** (zoom) riêng. Xoay vẫn tự phủ kín các góc như cũ.

## Mới trong 0.36.0

- **Căn chỉnh video overlay kiểu CapCut** (mục ✨ Overlay → nhóm *Căn chỉnh*):
  - **Lấp đầy / Vừa khung**, **Thu phóng** 10–400 %, **Vị trí X/Y**, lưới **căn 9 điểm**, **Xoay** (kèm nút ↺ 90° / ↻ 90°), **Lật** ngang / dọc, **↺ Đặt lại căn chỉnh**.
  - Khi mục Overlay đang mở: **kéo overlay ngay trên khung xem trước** để di chuyển, kéo ô vuông ở góc để đổi cỡ (cả khung thường lẫn khung thiết kế).
  - Áp dụng cho mọi overlay trong thư viện (overlay được chọn ngẫu nhiên vẫn nằm đúng chỗ), mọi kiểu hòa trộn (sáng, bình thường, tách nền xanh, overlay nền trong suốt) và mọi kiểu thời gian. Video xuất khớp vị trí với xem trước. Lưu cùng mẫu.
- **Bấm ra ngoài là bỏ chọn khung chữ**: đang kéo/chỉnh khung tiêu đề, nội dung, bấm vào chỗ trống quanh khung xem trước, vào hình (ngoài khung đang chọn) hoặc nhấn **Esc** thì khung và các nút kéo biến mất, về chế độ xem trước. Bấm vào thanh thuộc tính bên trái thì khung vẫn được chọn.
- **Bấm vào tiêu đề / nội dung trên xem trước là mở luôn mục thuộc tính** của lớp đó ở cột bên trái (khung nền → Nền & khung, lớp ảnh → Lớp ảnh), không phải tự tìm.
- **"Căn khung" của tiêu đề / nội dung căn theo khung nền**: các nút Sát trên / dưới / trái / phải / giữa giờ căn theo mép **khung nền** khi đang bật khung (trước đây căn theo cả màn hình video). Đổi lại bằng ô **Căn theo: Theo khung / Theo màn hình**.
- Sửa: nút ↺ 90° / ↻ 90° của Lớp ảnh trong bảng kiểu CapCut không chạy.

## Mới trong 0.35.1

- Sửa 🩺 Kiểm tra hệ thống đứng mãi ở "Đang kiểm tra…" (lúc máy còn đang kiểm tra nhanh khi mới mở app, bấm nút không chạy kiểm tra đầy đủ). Giờ bảng luôn chạy kiểm tra, đếm giây đang chờ, và báo rõ nếu quá 90 giây hoặc lỗi.
- Kiểm tra nhanh hơn: FFmpeg, card đồ họa, Demucs và 2 key chạy song song; thử key ai33 chỉ 1 lần, chờ tối đa 12 giây.

## Mới trong 0.35.0

- **🩺 Kiểm tra hệ thống** trên thanh trên cùng (cạnh 🔑 API key): chấm xanh = ổn, vàng = có mục cần chú ý, đỏ = có lỗi. Lúc mở app tự kiểm tra nhanh để tô màu chấm.
- Bấm vào để kiểm tra đầy đủ: Python, FFmpeg/FFprobe và các tính năng xuất video cần (chữ, H.264, MP3, nhạc nền tự giảm, hòa trộn lớp), libass (phụ đề chữ chạy), card đồ họa, Demucs, OpenAI key và ai33 key (thử thật 1 lần miễn phí, hiện số credit còn lại), thư mục xuất, dung lượng ổ đĩa, phông chữ, công cụ ghi thông tin file Windows.
- Mục lỗi xếp lên đầu, mỗi mục có **Cách sửa**; mục key có nút mở thẳng 🔑 API key. **📋 Copy báo cáo** để gửi khi cần hỗ trợ (báo cáo không chứa key).

## Mới trong 0.34.0

- **Khung xem trước vừa màn hình:** chiều cao khung tự tính theo chỗ trống thực tế của cửa sổ (trừ tiêu đề trang, thứ tự lớp, thanh phát), không còn cao quá màn hình laptop. Khung 16:9 / 1:1 tự lấy theo chiều ngang cột, không méo. Đổi cỡ cửa sổ là khung tự co giãn.
- **Thanh phát kiểu CapCut** (khung thường và khung thiết kế): thanh tua ở trên; bên dưới là thời gian · nút phát ở giữa · **Tỷ lệ ▾** và **⛶ toàn màn hình** bên phải.
- **Đổi khung ngay trên xem trước:** menu Tỷ lệ chọn 9:16 (TikTok, Reels), 16:9 (YouTube), 1:1, 4:5 hoặc Gốc; đổi luôn "Khung xuất" của video. Mẫu thiết kế (nền, khung, tiêu đề, nội dung) chỉ có 9:16 nên các tỷ lệ khác bị khóa khi đang bật.
- Thứ tự lớp gọn hơn; dòng hướng dẫn dưới xem trước rút còn 2 dòng (rê chuột để xem hết).
- Không còn báo nhầm "Lỗi giao diện: ResizeObserver loop…" (thông báo vô hại của trình duyệt khi khung tự co giãn).

## Mới trong 0.33.1

- **Xuất lại theo đúng nguồn chữ mới:** khi ✎ Sửa & xuất lại, đổi nguồn tiêu đề/nội dung sang Cố định, Tên file hoặc Không giờ có tác dụng (trước đây bị khóa theo lần chạy đầu, bật tiêu đề cố định lại ra tên file). Chọn "AI viết" mà video chưa có chữ AI: app báo và hiện nút "✍ Viết chữ AI (N video)" trên thanh Đang sửa (mỗi video 1 lần gọi OpenAI, giọng giữ nguyên).
- **Xuất lại theo đúng "Âm thanh gốc" mới:** đổi cách xử lý tiếng gốc (giảm khi có lời, lọc giọng giữa, Demucs, giữ, bỏ) hoặc mức "Tiếng gốc khi có lời" giờ làm lại bước tách âm (chạy trên máy, không tốn API) thay vì giữ tiếng nền cũ.
- **Chạy thử 1 video lỗi ngay khi nạp:** báo lý do và hiện lại nút chạy thử, không còn kẹt "Đang chạy thử…".
- **Thời gian còn lại ước tính đúng sau khi xuất lại:** chỉ tính thời gian của lần chạy gần nhất (trước đây cộng dồn).

## Mới trong 0.33.0 · rà soát lỗi, nút bấm, chồng chéo

**Lỗi đã sửa**
- Thêm/xóa/chép lớp ảnh trong mẫu thiết kế không còn báo "Lỗi giao diện" (hàm báo trạng thái còn ghi vào ô gợi ý của Timeline cũ đã gỡ).
- Báo thiếu key ai33 chỉ đúng chỗ: nút 🔑 API key (trước đây ghi "mục Âm thanh").
- Thanh báo lỗi chỉ báo lỗi của chính app, không báo nhầm lỗi của tiện ích trình duyệt (chặn quảng cáo, dịch trang…).
- Đang "✎ Sửa & xuất lại" mà thêm video mới: app tự thoát chế độ sửa (trả lại thông số trước đó) để video mới hiện và chạy đúng.

**Bớt chồng chéo, dễ hiểu hơn**
- Bỏ nút "⟳ Xuất lại ngay" trên thanh chọn (dễ áp nhầm thông số bên trái cho cả loạt); dùng "✎ Sửa & xuất lại".
- "Phụ đề tiếng Việt" đổi tên thành "File phụ đề .srt (không in lên hình)"; mục 💬 Phụ đề chữ chạy chuyển xuống ngay trên mục Xuất, hai loại phụ đề nằm cạnh nhau.
- "Lấp đầy · cắt viền" đổi tên thành "Lấp đầy · không viền (cắt phần thừa)".
- "Đặt lại lớp ảnh" đặt lại cả thứ tự lớp.
- Các nút Lớp ảnh (Vừa khung, Cỡ gốc, xoay, căn, xóa) báo "chọn ảnh trước" thay vì im lặng khi chưa chọn ảnh.

**Kiểm tra trước khi chạy đầy đủ hơn** (báo ngay, không đợi xuất xong): FFmpeg thiếu libass mà bật phụ đề chữ chạy · bật nhạc nền mà kho nhạc trống · bật lớp ảnh mà chưa chọn ảnh · phụ đề đè lên tiêu đề/nội dung · phụ đề nằm ở vùng TikTok che (dưới 80% hoặc sát thanh trên).

**Mới**
- Khi đang ✎ Sửa một video, khung xem trước chạy phụ đề chữ chạy bằng lời thật của video đó (thay cho câu mẫu).
- "Ghi đè file cũ khi xuất lại" (mục Xuất): xuất lại thay file cũ cùng tên thay vì sinh thêm -2, -3…
- Mở app bằng lối tắt ẩn mà cần tải FFmpeg: hiện hộp thông báo đang tải (trước đây tải im lặng).
- Dọn mã còn trỏ tới Timeline cũ đã gỡ.

## Mới trong 0.32.0

- **Tự cài FFmpeg và Python trên Windows:** bấm START_WINDOWS.bat là xong, không phải tự đi tìm.
  - Chưa có FFmpeg, hoặc bản đang có thiếu drawtext/libx264: app tự tải bản đầy đủ cho Windows (BtbN, dự phòng gyan.dev; khoảng 200 MB, có hiện % tiến độ, chỉ tải 1 lần) vào thư mục `bin` của ứng dụng, rồi chạy tiếp. Không cài vào hệ thống; xóa thư mục `bin` là gỡ. Bản này có sẵn libass (phụ đề chữ chạy) và NVENC.
  - Chưa có Python 3.11+: START_WINDOWS.bat tự cài Python 3.12 bằng winget (cho tài khoản đang dùng), rồi mở app.

## Mới trong 0.31.5

- **Tự báo lỗi giao diện:** trang chạy một bộ kiểm tra trước tiên. Trình duyệt quá cũ (thiếu tính năng app cần, ví dụ Edge đời cũ trên Windows 10 bản cũ) sẽ hiện thanh vàng nói rõ cần cài Chrome/Edge bản mới. Bất kỳ lỗi mã nào khiến nút bấm không chạy sẽ hiện thanh đỏ "⚠ Lỗi giao diện: …" kèm tên file và dòng lỗi, để chụp gửi người hỗ trợ (trước đây lỗi xảy ra im lặng, nút chỉ không phản hồi). Mất kết nối với ứng dụng cũng được báo.
- App không cần Node.js hay thư viện trình duyệt nào: chỉ cần Python 3.11+ và FFmpeg, mở bằng START_WINDOWS.bat (http://127.0.0.1:8000).

## Mới trong 0.31.4

- **Giữ đúng màu giao diện trên mọi trình duyệt:** trang khai báo sẵn là giao diện tối (color-scheme + darkreader-lock), nên chế độ tối tự động của Chrome/Cốc Cốc và tiện ích Dark Reader không tự đổi màu nữa (trước đây có máy thấy nút mất màu xanh, nền xám, viền trắng quanh mọi nút).

## Mới trong 0.31.3

- **Sửa lỗi dải mờ ở mép phải khi bật Lớp ảnh có chế độ hòa trộn** (ánh sáng dịu, nhân, màn hình…): một số bản FFmpeg (gặp trên Windows) xử lý bộ lọc hòa trộn theo từng khối 16 điểm ảnh và làm sai các cột lẻ còn lại. Khung 1080 px dư đúng 8 px, nên 8 px mép phải không được hòa trộn mà bị phủ tối bằng đúng độ mờ của lớp ảnh. Nay khung được nới thành bội số của 64 trước khi hòa trộn rồi cắt lại đúng kích thước, nên kết quả đúng trên mọi bản FFmpeg. Overlay video chế độ "Màn hình" cũng được sửa theo cách này.

## Mới trong 0.31.2

- **Hết vệt mờ chéo ở góc khi xoay video (lỗi cũ quay lại):** video tải về thường có sẵn dải mép mờ/tối rộng vài px. Khi không xoay, zoom 103% che dải này dọc 4 cạnh. Khi xoay 0,5°, 4 góc chỉ còn chừa 2px nên dải mép bị kéo vào góc thành vệt chéo, kể cả khi đã "Cắt viền mép 2px". Nay khi xoay, app giữ ở góc đúng phần dư mà zoom tạo ra (phóng thêm khoảng 1–2%), nên xoay không bao giờ làm lộ mép nhiều hơn lúc không xoay. Áp dụng cho Khung xuất, video trong mẫu thiết kế và khung xem trước. Có test với video có mép mờ 6px.

## Mới trong 0.31.1

- **Sửa & xuất lại dùng luôn danh sách "Video đầu vào":** tick video ở hàng đợi rồi bấm "✎ Sửa & xuất lại" (hoặc "✎ Sửa" trên một dòng), các video đó hiện ở mục 🎬 Video đầu vào. Bấm từng dòng để xem trước video đó; nút chính trên cùng đổi thành "⟳ Xuất lại N video". Bấm "✕ Thoát sửa" để trả lại danh sách video và thông số trước đó.
- Video trùng tên AI hiện thêm tên file gốc để dễ phân biệt.
- Đảm bảo xuất lại theo thông số mới: mỗi lần bấm "Xuất lại", thông số đang chỉnh bên trái (khung, zoom, xoay, màu, nền, chữ, phụ đề, lớp, nhạc, độ phân giải…) được ghi vào video rồi mới render. File mới đúng thông số mới, file cũ giữ nguyên; giọng và chữ không làm lại. Có test kiểm tra.

## Mới trong 0.31.0

**✎ Sửa & xuất lại (không gọi lại API)**
- Ở mỗi video xong / lỗi / tạm dừng trong hàng đợi có nút "✎ Sửa": app nạp lại thông số của video đó vào bên trái, mở video gốc ở khung xem trước để chỉnh trực quan (khung, zoom, xoay, màu, nền, chữ, phụ đề chữ chạy, lớp ảnh, overlay, nhạc nền, thông số xuất), rồi bấm "⟳ Xuất lại video này".
- Sửa hàng loạt: tick nhiều video rồi bấm "✎ Sửa & xuất lại" trên thanh chọn. Khung xem trước hiện video đầu tiên; "⟳ Xuất lại N video" xuất lại tất cả với cùng thông số. Có nút "＋ Thêm video đã tick" để thêm video vào lần sửa đang làm.
- Chỉ đổi phần hình và tiếng nền. Lời nhận diện, bản dịch, tiêu đề / nội dung AI, giọng đọc và cắt đầu / cuối giữ nguyên, nên không tốn thêm tiền OpenAI hay credit ai33. Dù bên trái đang để văn phong, giọng hay chế độ khác, các thông số đó cũng không bị đổi khi xuất lại.
- Mỗi lần xuất lại tạo file mới trong thư mục xuất (file cũ không bị ghi đè). Bấm ✕ để thoát sửa và trả lại thông số trước đó.
- Thêm video cũ vào lại (bật "Dùng lại kết quả cũ") vẫn dùng lại được giọng và chữ như trước; nút "✎ Sửa" nhanh hơn vì không cần chọn lại file.

## Mới trong 0.30.3

- **Sửa lỗi mất nút căn ở "Cắt & vị trí video" (khi không dùng mẫu thiết kế):** dòng "Căn" trống và hàng nút nhanh (⊕ Giữa, xoay 90°, lật, Zoom 110%, Đặt lại) biến mất vì bị ẩn nhầm khi dựng khung CapCut. Nay hiện lại đủ lưới căn 9 ô và hàng nút nhanh. Chế độ có mẫu thiết kế vẫn có "⊕ Giữa khung" như trước.

## Mới trong 0.30.2

- **Nút chạy gọn một hàng:** "🧪 Chạy thử 1" và "▶ Lồng tiếng N video" ghép thành một cụm nút trên thanh trên cùng (không còn nút chạy thử dài cả hàng, nút chính rớt xuống dòng dưới). Khi đang xếp hàng, cả hai nút cùng khóa.

## Mới trong 0.30.1

- **Sắp lại các mục theo đúng trình tự làm việc:** 🎬 Video đầu vào → Nhận diện, dịch & viết chữ → Giọng đọc ai33 → Âm thanh gốc → Nhạc nền → Cắt & vị trí video → Điều chỉnh màu → Nền & khung → Tiêu đề → Nội dung → Phụ đề chữ chạy → Lớp ảnh → Overlay ngẫu nhiên → Xuất & chạy hàng loạt. Trước đây "Phụ đề chữ chạy" và "Nhạc nền" bị nằm trên cả "Video đầu vào".

## Mới trong 0.30.0

**💬 Phụ đề chữ chạy (mới, có công tắc)**
- Phụ đề in thẳng lên video, mỗi lần vài chữ, từ đang đọc sáng lên theo giọng đọc tiếng Việt (giống phụ đề tự động của CapCut).
- 9 kiểu hiệu ứng: Viền đen, Nền hộp, Phóng to từ, Phát sáng, Karaoke tô dần, Nền màu từ, Bóng đổ, Hiện dần, Từng chữ.
- 12 mẫu nhanh, mỗi mẫu đặt sẵn kiểu, phông và màu chỉ với 1 lần bấm (TikTok vàng, Hộp đen, Pop xanh, Neon hồng, Karaoke, Marker đỏ, Bóng đổ, Hiện dần, Từng chữ, Viết tay, Truyện tranh, Dễ thương).
- Chỉnh phông, số chữ mỗi lần, cỡ chữ, vị trí dọc (kéo chữ mẫu trên khung xem trước), màu chữ, màu từ đang đọc, viết hoa.
- Khung xem trước chạy một câu mẫu với đúng kiểu và màu đã chọn, vì chữ thật chỉ có sau khi AI dịch xong. Video xuất dùng đúng lời đọc của từng video.
- Cần FFmpeg có libass (bản "full"). Nếu thiếu, video vẫn xuất nhưng không có phụ đề, và hàng đợi báo rõ lý do.

**🆕 7 phông chữ mới có đủ dấu tiếng Việt:** Montserrat, Nunito, Lexend, Oswald, Baloo 2, Quicksand, Fira Sans. Dùng được cho phụ đề và cho tiêu đề / nội dung.

**🎶 Nhạc nền (mới, có công tắc)**
- Kho nhạc riêng: thêm MP3/WAV/M4A…, nghe thử, xóa, gắn văn phong cho từng bài.
- Mỗi video tự chọn 1 bài hợp văn phong của nó (không có thì lấy bài chưa gắn, rồi bất kỳ bài nào). Tick "Dùng" để giới hạn những bài được chọn.
- Bài dài bắt đầu ở một đoạn ngẫu nhiên, bài ngắn tự lặp; có lên và xuống nhỏ dần ở đầu, cuối.
- Chỉnh được âm lượng; "Tự giảm nhạc khi có giọng đọc" làm nhạc nhỏ đi khi đang nói.
- Bài đã chọn được giữ cho video đó: xuất lại vẫn đúng bài cũ.

**🧪 Chạy thử 1 video**
- Có từ 2 video trở lên thì hiện nút "Chạy thử 1 video": chạy riêng video đầu tiên.
- Xong sẽ hiện thanh "Xem video thử" và "Ưng rồi · chạy N video còn lại". Chưa ưng thì sửa thông số rồi bấm chạy thử lại.

## Mới trong 0.29.0

**Thứ tự lớp (mới)**
- Ô "Thứ tự lớp" ngay dưới khung xem trước: 🎬 Video · 🎨 Nền · ✨ Video overlay · 🖼 Lớp ảnh, xếp từ trên cùng xuống dưới cùng; bấm ‹ › để đưa một lớp lên hoặc xuống, ↺ về mặc định. Khung trang trí và chữ luôn nằm trên cùng.
- Xem trước đổi ngay khi sắp xếp, video xuất ra đúng thứ tự đó; thứ tự lưu cùng mẫu cấu hình.
- Không dùng mẫu thiết kế thì video phủ cả khung nên luôn ở dưới cùng; chỉ đổi được thứ tự Lớp ảnh và Overlay.

**Hàng đợi thiết kế lại**
- Thanh tổng quan: tiến độ cả lô (xong / đang chạy / chờ / chờ duyệt / lỗi), thời gian còn lại ước tính, thời gian trung bình mỗi video, OpenAI đã dùng và credit ai33 còn lại.
- Thanh công cụ gọn: "↻ Chạy lại lỗi" và "■ Dừng tất cả"; dọn file tạm, xóa và "🔔 Báo khi cả lô xong" nằm trong menu ⋯.
- Tick chọn nhiều video: Chạy, Dừng, ⤒ Ưu tiên / ⤓ Xuống cuối trong hàng chờ, ⟳ Xuất lại với thông số mới (giữ giọng và chữ đã có), Xóa. Video đang chờ hiện số thứ tự "Chờ · #3"; video đang chạy hiện bước đang làm.
- Tìm theo tên video và lọc video kẹt ở từng bước.
- Lỗi được gom nhóm theo nguyên nhân, kèm cách xử lý và nút "Chạy lại nhóm".
- Báo khi cả lô xong: âm báo, thông báo trên máy và dòng tóm tắt.
- Sửa lỗi: "Chạy lại lỗi" trước đây chạy luôn cả video đang chờ duyệt (xuất khi chưa xem chữ AI); nay chỉ chạy video lỗi. Nút xóa không còn sáng khi hàng đợi trống. Mọi thao tác hàng loạt gửi một lần cho server (nhanh với hàng trăm video).

**Văn phong viết hay hơn**
- Mỗi văn phong có hồ sơ riêng: giọng, câu mở 3 giây đầu, trình tự ý, từ nên dùng / cần tránh, câu mẫu. Gửi đầy đủ khi viết đoạn văn lồng tiếng và tiêu đề / nội dung; bản dịch theo từng dòng (phải khớp thời gian) chỉ dùng câu ngắn để câu không dài ra.
- Mới: "Độ hào hứng" (Nhẹ nhàng / Vừa phải / Hào hứng) dùng chung mọi văn phong.
- Kiểu tiêu đề "Tự chọn" theo văn phong (Tin tức không dùng kiểu nỗi đau – giải pháp, Giải trí ưu tiên gây tò mò…).
- Sửa mâu thuẫn: "Trải nghiệm thực tế" chỉ kể trải nghiệm có trong lời gốc; bỏ câu trùng về thông số ở "Công nghệ".

## Mới trong 0.28.2

- **Xem trước cập nhật ngay khi bỏ video đầu vào:** bỏ hết video (✕ hoặc "Bỏ tất cả") thì khung xem trước trống ngay, không còn giữ video cũ; áp dụng cho cả khung thiết kế và khung thường.

## Mới trong 0.28.1

- **Hết cảnh báo "Windows chưa ghi được: Copyright (Access Denied)":** Copyright đã được ghi khi xuất video (thẻ MP4 mà Windows đọc ra ở mục Copyright), bước ghi của Windows chỉ thử ghi đè lần nữa và bị Windows khóa. Nay bỏ lần ghi thừa đó; Copyright vẫn hiện đúng trong Properties → Details.

## Mới trong 0.28.0

- **Xem số dư ngay trên thanh chạy (tab Lồng tiếng):** ô key hiện `OpenAI ✓ · đã dùng $1.23 | ai33 ✓ · còn ◆ 123.457`.
  - **ai33:** số credit còn lại lấy trực tiếp từ ai33.pro.
  - **OpenAI:** OpenAI không cho xem số dư bằng API key thường, nên app tự cộng chi phí các lần gọi của chính app trong tháng (token thực tế × bảng giá, Whisper theo phút). Đây là ước tính; số dư thật xem ở platform.openai.com → Billing. Rê chuột lên ô để xem chi tiết.
  - Tự cập nhật mỗi phút, sau mỗi video xong và khi bấm vào ô.
- **Lớp ảnh và Overlay ngẫu nhiên có công tắc bật/tắt ở tiêu đề**, giống Nền & khung / Tiêu đề / Nội dung / Điều chỉnh màu. Tắt thì giữ nguyên mọi thông số, chỉ không chèn vào video.

## Mới trong 0.27.6

- **Hết viền mờ / viền đen ở cạnh khi chọn "Giữ toàn bộ":** "Cắt viền mép" làm video 9:16 lệch tỷ lệ một chút (1080×1920 → 1072×1912), nên "Giữ toàn bộ · viền đen" để lại dải đen 1–2 px và "Giữ toàn bộ · nền mờ" để lại dải mờ ở hai cạnh. Nay video gần đúng tỷ lệ khung (lệch ≤ 3%) luôn được phủ kín như "Lấp đầy", kể cả khi xoay; video khác hẳn tỷ lệ (16:9, 1:1…) vẫn giữ toàn bộ như cũ. Áp dụng cho Khung xuất, video trong mẫu thiết kế và khung xem trước.

## Mới trong 0.27.5

- **Hết góc đen / viền mờ khi xoay video:** ở chế độ "Lấp đầy · cắt viền", xoay nhẹ (vd 0,5°) cộng với dịch X/Y làm lộ góc đen dù đã zoom 103%. Nay app tự phóng thêm vừa đủ (thường chỉ 0,5–2%) để video luôn phủ kín khung, kể cả mép mờ do xoay; áp dụng cho cả "Khung xuất" ở tab Lồng tiếng và video trong mẫu thiết kế, xem trước khớp với bản xuất. Video bạn chủ động thu nhỏ hơn khung vẫn giữ nguyên.

## Mới trong 0.27.4

- **Sửa lỗi "UnicodeEncodeError: 'charmap' codec…" khi ghi thông tin file:** bước ghi của Windows in thông báo tiếng Việt ra cửa sổ lệnh không hỗ trợ chữ có dấu nên bị lỗi và che mất tên trường bị từ chối. Nay luôn in UTF-8: hàng đợi báo đúng "Windows chưa ghi được: <tên trường> (lý do)", các trường khác vẫn được lưu.

## Mới trong 0.27.3

- **Tên file dài hơn:** AI đặt tên 30–45 ký tự (khoảng 6–9 từ: loại sản phẩm + 2–3 đặc điểm), ví dụ `tui-vai-dung-quan-ao-gap-gon-chong-am`. Tên bị cắt không bao giờ kết thúc bằng từ nối (-cho, -va, -cua…). Sửa tay cũng theo giới hạn mới.
- **Contributing artists để trống:** bỏ trường Authors (Windows hiện trường này thành Contributing artists của nhóm Media). Tác giả chỉ vào Directors / Producers / Writers.

## Mới trong 0.27.2

- **Sửa lỗi metadata Windows không ghi** (chỉ có Title và ngày): bản pywin32 trên máy không có hằng `pscon.GPS_READWRITE` nên bước ghi dừng ngay. Nay dùng giá trị 2 như script gốc; mỗi trường thử kiểu chữ LPWSTR rồi BSTR. Tags, đánh giá, Directors, Producers, Writers, Publisher, Content provider, Author URL, Promotion URL được ghi.
- **Trả lại các nút của mục Cắt & vị trí video** bị mất ở 0.27.0: căn trái / giữa ngang / phải / trên / giữa dọc / dưới, **⊕ Giữa khung**, kích thước nhanh (Lấp đầy 9:16, Giữ toàn bộ hình, Vừa chiều ngang / dọc), zoom 100–200 %, xoay 90° / 180°.
- **Cắt viền mép video gốc** (0–40 px mỗi cạnh): bỏ mép nhòe hoặc viền sáng / đen của video tải về trước khi đặt vào khung; thường 2–6 px là đủ. Lưu trong mẫu.

## Mới trong 0.27.1

- **Sửa lỗi thông tin file trống ở nhóm Origin:** Windows từ chối kiểu dữ liệu chữ cũ nên cả lần ghi bị hủy (Directors, Producers, Writers, Publisher, Author URL, Promotion URL trống). Nay dùng đúng kiểu, ghi từng trường riêng: trường nào Windows từ chối thì báo tên trong hàng đợi, các trường khác vẫn lưu.
- **Không ghi nhóm Media:** bỏ Contributing artists (trước bị tách link thành "https:; www.tiktok.com; …") và Year. Tác giả → Directors / Producers / Writers; Link kênh → Author URL / Promotion URL; Nhà phát hành → Publisher / **Content provider** (mới). Hộp xuất ghi rõ ô nào vào trường nào.

## Mới trong 0.27.0

- **Thông số xuất áp dụng thật cho video hàng loạt:** độ phân giải (720p / 1080p / 2K / 4K hoặc **Theo video gốc**), khung hình tối đa (30 / 60 fps: nguồn 60 fps → 30 fps, nguồn 25 fps giữ 25), chất lượng (tiêu chuẩn / cao). Trước đây hộp này chỉ có bộ mã hóa là có tác dụng.
- **Một chỗ cho mọi thông số xuất:** Bộ mã hóa và Âm lượng tổng chỉ còn trong hộp Thông số video xuất; mục "Xuất & chạy hàng loạt" hiện tóm tắt và nút "Thông số xuất ›".
- **Cắt đầu / cuối không nén thêm lần nào:** đoạn cắt được áp ngay khi đọc video gốc, chỉ nén 1 lần lúc xuất (nhanh hơn, giữ chất lượng).
- **Mỗi video chỉ lưu 1 bản:** thư mục xuất cùng ổ đĩa thì dùng liên kết cứng (không tốn thêm chỗ); khác ổ đĩa thì chỉ giữ bản trong thư mục xuất. Xuất lại không bao giờ ghi vào file đã lưu trước.
- **Không xóa video gốc còn trong hàng đợi chưa xong** khi tự dọn video cũ sau 30 ngày.
- **Tự chạy tiếp khi mở lại ứng dụng** (tắt được): video đang chờ / đang chạy dở được xếp lại hàng với key đã lưu, không mua giọng trùng.
- **Nhanh hơn khi chạy nhiều video:** CPU chia hết số nhân cho các video đang xuất (trước cố định 2 luồng); **Tách giọng AI (Demucs) cùng lúc** chọn được 1–4 video (mặc định 1, tránh hết RAM/VRAM); hàng đợi chỉ gửi phần thay đổi thay vì cả danh sách mỗi 1,5 giây.
- **Dọn file tạm:** nút 💾 trong hàng đợi hiện dung lượng file tạm và dọn của video đã xong (giữ giọng đọc, bản dịch, video xuất); tự dọn video xong quá 3 ngày. Xuất lại sau khi dọn tự tạo lại nhạc nền / giọng trộn, không gọi lại AI hay ai33.
- **Từ điển phát âm chọn theo tên** (tải từ tài khoản ai33) thay vì gõ ID.
- **Phím tắt trên khung xem trước:** Ctrl+Z / Ctrl+Y hoàn tác thiết kế, Alt + mũi tên dịch hộp đang chọn.
- Gỡ trình dựng 1 video cũ (timeline, kho media, xuất lô kiểu cũ…) còn tải ngầm; tài liệu viết lại theo luồng hiện tại.

## Mới trong 0.26.1

- **Ngày tạo trong thông tin file lùi ngẫu nhiên** (Thông số video xuất → Thông tin file → Ngày tạo): mặc định lùi 5–7 ngày so với ngày xuất, mỗi video một ngày ngẫu nhiên (ví dụ xuất ngày 15/7/2026 → ngày tạo 8/7 đến 10/7/2026). Xuất lại giữ nguyên ngày đã chọn; đặt 0 – 0 để dùng ngày xuất. Lưu trong mẫu.

## Mới trong 0.26.0

- **Sửa tên file tay:** mở một video trong hàng đợi → ô **Tên file** → Đổi tên (gõ có dấu cũng được, app tự đổi sang dạng `ten-khong-dau`, xem trước tên `.mp4`). Video đã lưu trong thư mục xuất được đổi tên luôn (cả file `.srt`), không bao giờ ghi đè file khác. Bảng **Duyệt chữ AI** có ô tên file cho từng video. Tên gõ tay không bị AI thay khi viết lại chữ.
- **Tiêu đề có dấu trong thông tin file:** AI trả thêm tên video tiếng Việt có dấu (30–80 ký tự) trong cùng lần gọi, dùng cho Title của file (ví dụ "Đệm lót giày TPU mềm gót, tiện lợi khi vận động"); hàng đợi hiện kèm tiêu đề file và tags.

## Mới trong 0.25.0

- **Hộp "Thông số video xuất" chia nhóm** như các mục khác: Video · Âm thanh · Lưu file · Thông tin file.
- **Thông tin file (metadata), có công tắc bật/tắt**, lưu trong mẫu:
  - Không chép metadata của video gốc (link, thiết bị, tiêu đề cũ của người khác).
  - Tiêu đề = tiêu đề AI viết (hoặc tên file); Tags = 3–6 từ khóa AI viết **trong cùng lần gọi dịch**; ngày tạo = ngày xuất.
  - Cố định cho cả lô: Tác giả (cũng ghi vào Directors / Producers / Writers), Link kênh (Author URL + Promotion URL), Nhà phát hành, Bản quyền, Đánh giá sao.
  - Không ghi "Encoded by".
  - Tiêu đề, tác giả, bản quyền, năm ghi bằng FFmpeg; Tags, đánh giá, link kênh, nhà phát hành ghi bằng Windows sau khi xuất (tự cài pywin32 lần đầu, cần Internet; lỗi thì chỉ cảnh báo, video vẫn xuất).

## Mới trong 0.24.0

- **Bỏ tab Dịch & biên tập AI** (cùng chế độ Thủ công và Gemini): việc dịch, tiêu đề, nội dung, tên file đã tự chạy cho từng video trong tab Dựng & lồng tiếng. Thanh trên còn 2 tab; hộp API key chỉ còn OpenAI và ai33 (key Gemini đã lưu được xóa khỏi máy).
- **Sửa mẫu câu lệnh ngay trong tab Dựng:** link "Sửa mẫu ›" mở hộp sửa: chọn / lưu nhiều mẫu, xóa, khôi phục mặc định, xem phần luôn được thêm. Mẫu mặc định chỉ còn quy tắc nội dung; mẫu cũ của bạn vẫn dùng được (phần hook/kịch bản tự bỏ khi gửi).
- **Mẫu câu lệnh lưu cùng "Lưu mẫu":** mỗi mẫu dựng nhớ luôn câu lệnh của nó, chọn mẫu là đổi cả giao diện lẫn câu lệnh.
- **Gợi ý chung cho cả lô:** ô 💡 ở đầu danh sách video, dùng khi cả lô cùng một sản phẩm; video có gợi ý riêng thì dùng gợi ý riêng.
- Tab Âm thanh bỏ nút "Lấy kịch bản AI" (lấy từ tab đã bỏ).

## Mới trong 0.23.0

- **AI xem hình:** mỗi video gửi kèm 3 khung hình nhỏ ngay trong lần gọi dịch (không thêm lần gọi), AI nhận đúng sản phẩm cho tiêu đề, nội dung và tên file. Video không có lời (tab Dựng) vẫn được AI viết chữ theo hình. Model không nhận ảnh thì tự gọi lại không kèm ảnh.
- **Gợi ý sản phẩm từng video** (nút 💡 trong danh sách video, không bắt buộc): AI dùng làm căn cứ chính; tên file gốc cũng được gửi để tham khảo.
- **3 tiêu đề + 2 nội dung** dài ngắn khác nhau trong cùng lần gọi; app tự chọn phương án dài nhất vừa giới hạn ký tự, không có giá/thông số, không kết thúc bằng từ nối (chỉ cắt chữ khi không phương án nào vừa). Đổi phương án bằng nút số trong hàng đợi và bảng duyệt; ô có vấn đề được tô màu cảnh báo.
- **Kiểu tiêu đề:** AI tự chọn, câu hỏi, nỗi đau → giải pháp, lợi ích chính, gây tò mò (lưu trong mẫu).
- **Câu lệnh gọn hơn:** tab Dựng chỉ gửi phần quy tắc nội dung của mẫu (bỏ phần hook/kịch bản/định dạng), mẫu mặc định ngắn đi khoảng 60%.
- **2 tên file:** tên chính và tên dự phòng; trùng tên thì dùng tên dự phòng trước rồi mới thêm -2, -3.
- **Tự thử lại khi lỗi mạng:** OpenAI thử lại tối đa 3 lần (mất kết nối, quá tải, lỗi 5xx; không thử lại khi hết quota). ai33 thử lại khi đọc trạng thái; lệnh tạo giọng chỉ thử lại khi chắc chắn chưa được nhận, không bao giờ mua trùng.
- **Dùng lại kết quả cũ:** chạy lại cùng một video (nhận diện theo nội dung file) mà chỉ đổi giao diện, màu, overlay, tốc độ… thì dùng lại lời gốc, bản dịch, chữ AI và giọng đọc, không tốn API. Đổi giọng thì giữ bản dịch, chỉ tạo lại giọng; đổi giới hạn chữ thì chỉ viết lại chữ. Tắt được ở mục Nhận diện & dịch.
- **Ước tính chi phí chính xác hơn:** hộp kiểm tra trước khi chạy tính theo độ dài câu lệnh thật, ảnh khung hình và phần được dùng lại.
- **Nghe thử giọng:** nút ▶ Nghe thử đọc một câu (câu mẫu hoặc câu tự gõ) bằng giọng, tốc độ, từ điển đang chọn; lưu lại nên nghe lại không tốn credit.
- **Tab Dịch & biên tập AI thiết kế lại:** 3 cột (cài đặt kiểu CapCut · nguồn · kết quả), dùng cùng giới hạn ký tự, kiểu tiêu đề, 3 tiêu đề / 2 nội dung và tên file như tab Dựng; có ô gợi ý sản phẩm và nút "Lấy theo tab Dựng".

## Cách dùng (tóm tắt)

1. **API key** (nút trên thanh trên): OpenAI và ai33.pro, lưu trong `.local/` trên máy này, không đưa vào ZIP. Không gửi key trong chat.
2. **Video đầu vào:** kéo thả, chọn file hoặc cả thư mục trên máy (không chép, dùng liên kết). Nút 💡: gợi ý sản phẩm cho từng video hoặc cho cả lô.
3. **Nền & khung, Tiêu đề, Nội dung, Cắt & vị trí video, Điều chỉnh màu, Overlay, Lớp ảnh:** mỗi nhóm có công tắc; khung xem trước cập nhật ngay, kéo thả trực tiếp.
4. **Nhận diện, dịch & viết chữ:** văn phong, xưng hô, model, cho AI xem 3 khung hình, dùng lại kết quả cũ, **Sửa mẫu ›** câu lệnh.
5. **Giọng đọc ai33:** chọn giọng, ▶ Nghe thử, từ điển phát âm, khớp tốc độ giọng ↔ video.
6. **Thông số video xuất** (nút trên thanh trên): độ phân giải, fps, chất lượng, bộ mã hóa, âm lượng, thư mục lưu, thông tin file (metadata).
7. **Lưu mẫu** lưu mọi thông số trên (cả câu lệnh). **Bắt đầu** → hộp kiểm tra chi phí → hàng đợi chạy; duyệt chữ hàng loạt nếu bật.

## Chạy và cập nhật

Cần Python 3.11+ và FFmpeg/FFprobe (libx264, drawtext, libmp3lame). Không cần pip/npm (riêng ghi Tags/đánh giá của Windows tự cài pywin32 lần đầu; Demucs cài bằng nút trong app).

```sh
python3 launch.py
```

Windows: `START_WINDOWS.bat`. Cổng mặc định 8000 (`PORT` để đổi). Cập nhật: nút ⟳ trong app hoặc `UPDATE_WINDOWS.bat`; dữ liệu trong `.local/` được giữ.

## Dữ liệu

`.local/` chứa video nguồn, hàng đợi (`.local/dub/<id>/job.json` cùng giọng đọc và bản dịch), MP3, mẫu, key đã lưu. Video gốc không dùng quá 30 ngày tự xóa khi mở app (`REVIEW_KEEP_DAYS=0` để tắt), trừ video còn trong hàng đợi chưa xong. Chỉ dùng trên máy này (localhost).

## Kiểm chứng

```sh
python3 -m unittest discover -s tests
```

Pipeline lồng tiếng được kiểm tra với FFmpeg thật và OpenAI / ai33 giả lập (HTTP), giao diện bằng Chromium. Chưa gọi OpenAI / ai33 thật, chưa thử NVENC và Windows Property Store trên máy thật.

## Phát hành bản mới (cho người bảo trì)

1. Sửa code, tăng `VERSION`, thêm mục "Mới trong …" ở đầu README.
2. `python build_package.py --manifest` (cập nhật `MANIFEST.json`).
3. `python -m unittest discover -s tests`, rồi commit và push lên `main`.
4. Người dùng bấm ⟳ trong ứng dụng hoặc chạy `UPDATE_WINDOWS.bat`.

## Gemini (nhánh tích hợp provider)

- Cài SDK chính thức vào cùng Python chạy ứng dụng: `python -m pip install -r requirements-gemini.txt`, sau đó `python launch.py --no-browser` (Windows có thể mở như trước, dùng đúng Python đã cài SDK). OpenAI cũ không cần SDK này.
- Tạo API key trong Google AI Studio: https://aistudio.google.com/apikey. Nhập ở **API key → Gemini → Lưu**. Key được giữ trong `.local/secrets.json`, không nằm trong ZIP; giao diện chỉ nhận trạng thái và bốn ký tự cuối. Không chia sẻ key trong chat.
- Bấm **Kiểm tra Gemini** hoặc **Làm mới model Gemini**. Backend dùng SDK `models.list`, chỉ nhận model có `generateContent`, lưu danh sách và thời điểm kiểm tra trong `.local/gemini-models.json`. Kết quả này xác nhận danh sách, không bảo đảm mọi yêu cầu generate/JSON của tài khoản đều thành công.
- Chọn **Nhà cung cấp dịch / biên tập → Gemini**, model chính và (tùy chọn) model dự phòng. Fallback chỉ chuyển giữa các model Gemini đã có trong danh sách, tối đa ba lần thử mỗi model; không tự chuyển sang OpenAI. 401/403/404, payload hoặc JSON sai không retry. 429/5xx/lỗi mạng tạm thời retry có giới hạn, tôn trọng Retry-After; thời gian chờ trên 60 giây trả lỗi để tiếp tục sau. Có thể hủy lúc chờ; một request đang gửi có thể phải chờ timeout.
- Các tên yêu cầu **Gemini 3.5 Flash Lite, 3.1 Flash Lite, 3.6 Flash, 3.8 Flash chưa được xác minh**. Không gán ID suy đoán. Khi danh sách đã được kiểm tra và có key, giao diện mới ưu tiên một Flash-Lite/Flash thực sự được liệt kê. Cấu hình cũ thiếu provider vẫn là OpenAI.
- STT vẫn dùng **OpenAI Whisper** với key riêng; Gemini chỉ dịch/biên tập; giọng đọc vẫn là ai33.pro. SRT giữ timestamp bằng code. Không có tuyên bố toàn bộ pipeline miễn phí.
- **Thống kê token Gemini** hiển thị thống kê theo ngày UTC/model: logical tasks, attempts, retries, thành công/thất bại, 429, token từ usage metadata và thời điểm gần nhất. `missing_usage` ghi số phản hồi không có usage; số 0 của bộ cộng token không có nghĩa là miễn phí. OpenAI vẫn có thống kê chi phí cũ; chưa hợp nhất thống kê attempt OpenAI vào bảng Gemini. Cache/checkpoint không tạo attempt mới.
- Provider và cấu hình fallback được lưu cùng cấu hình/mẫu và tham gia khóa cache dịch; đổi provider không làm mất cache STT. Chi phí Gemini chưa được ước tính; tổng trước khi chạy chỉ gồm Whisper và ai33 khi chọn Gemini. Quota phụ thuộc tài khoản, không hardcode các con số tham khảo.
- Mạng cần cho phép `generativelanguage.googleapis.com` để dùng Gemini; cài SDK cần PyPI. Không lưu khóa thật trong repository hoặc manifest.

Kiểm thử: `python -m unittest discover -s tests -v`. Các test Gemini dùng API giả lập; chưa kiểm thử generateContent thật, trình duyệt trên Windows, GPU và Windows Property Store. Hai lỗi FFmpeg đã có ở baseline môi trường Linux (FPS 72 thay vì 60; chênh pixel blend 33 thay vì ≤2) cần xử lý riêng. Bản tích hợp chưa thay đổi thuật toán cân thời lượng/cắt giọng hiện có.
