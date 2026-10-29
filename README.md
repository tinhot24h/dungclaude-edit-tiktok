# Review Studio 0.27.4

Làm video review / lồng tiếng TikTok **hàng loạt** trên máy Windows: chọn nhiều MP4 tiếng Trung → OpenAI nhận diện lời, dịch, viết tiêu đề / nội dung / tên file → ai33.pro đọc giọng Việt → FFmpeg ghép nền, khung, chữ, overlay và xuất MP4 hoàn chỉnh vào thư mục của bạn.

**Tải bản đóng gói:** mục [Releases](https://github.com/tinhot24h/dungclaude-edit-tiktok/releases) · Cài và chạy: `HUONG_DAN.txt`.

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
