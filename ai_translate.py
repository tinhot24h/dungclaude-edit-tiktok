"""Shared writing rules for the AI calls of the dubbing queue: styles, the default template (content rules only;
the queue adds its own role, limits and output format) and the always-on rule against prices, brands and specs."""
import re

DEFAULT_MODEL = 'gpt-4.1-mini'
STYLES = {
    'review': 'Review sản phẩm: gần gũi, mô tả đặc điểm và cách dùng, không giả vờ đã trải nghiệm.',
    'news': 'Tin tức: trung tính, thông tin chính trước, phân biệt sự kiện với nhận định, giữ nguồn nếu có.',
    'tips': 'Chia sẻ mẹo: nêu vấn đề, hướng dẫn ngắn gọn, kết quả chỉ trong phạm vi nguồn cung cấp.',
    'intro': 'Giới thiệu sản phẩm: mạch lạc, dễ hiểu, nhấn lợi ích đã được nguồn nêu, không cường điệu.',
    'household': 'Gia dụng · đồ dùng nhà cửa: mở từ chuyện sinh hoạt hằng ngày (dọn dẹp, nấu nướng, cất đồ, giặt giũ), nói rõ dùng thế nào và tiện ở đâu, giọng gần gũi như người trong nhà mách nhau; nhấn sạch sẽ, gọn gàng, tiết kiệm thời gian, an toàn cho gia đình; không phóng đại công dụng.',
    'experience': 'Trải nghiệm thực tế: kể theo trình tự dùng thử (mở hộp → dùng → cảm nhận), nói cả điểm hay lẫn lưu ý mà nguồn nêu, câu ngắn tự nhiên như đang quay vlog; chỉ dùng trải nghiệm có trong nguồn, không tự bịa cảm nhận.',
    'beauty': 'Làm đẹp · chăm sóc: nhẹ nhàng, tinh tế, chú trọng cảm giác khi dùng, cách dùng và thói quen chăm sóc; tuyệt đối không cam kết hiệu quả điều trị, không dùng từ y khoa khẳng định.',
    'tech': 'Công nghệ · đồ điện tử: rõ ràng, đi thẳng vào tính năng và lợi ích khi dùng, giải thích dễ hiểu cho người không rành kỹ thuật; nói chung chung về cấu hình, không đọc thông số.',
    'food': 'Ẩm thực: gợi hình gợi vị (giòn, thơm, đậm đà…), kể cách làm/cách ăn theo thứ tự, giọng hào hứng vừa phải.',
    'fashion': 'Thời trang: nói về phong cách, cách phối, chất liệu và cảm giác mặc, gợi ý dịp dùng; giọng trẻ trung, có gu.',
    'fun': 'Giải trí · hài hước: nhịp nhanh, câu ngắn, dí dỏm, có thể dùng từ trend phổ biến nhưng không thô tục, không xúc phạm.',
}
# Labels of the style picker in the dubbing tab.
STYLE_LABELS = {'review': 'Review sản phẩm', 'household': 'Gia dụng · nhà cửa', 'experience': 'Trải nghiệm thực tế', 'news': 'Tin tức · thời sự',
                'tips': 'Chia sẻ mẹo', 'intro': 'Giới thiệu sản phẩm', 'beauty': 'Làm đẹp · chăm sóc', 'tech': 'Công nghệ · điện tử',
                'food': 'Ẩm thực', 'fashion': 'Thời trang', 'fun': 'Giải trí · hài hước'}

# Editable template (Mẫu câu lệnh, edited in the Dựng & lồng tiếng tab): content rules only.
DEFAULT_RULES = '''QUY TẮC NỘI DUNG
- Giữ đúng sự thật, đặc điểm, đơn vị và mức độ chắc chắn của nguồn. Không bịa công dụng, nguồn tin, bằng chứng hoặc trải nghiệm cá nhân.
- Với văn phong review, không tự thêm câu "mình đã dùng", "mình đã thử" nếu nguồn không đủ căn cứ; không gán trải nghiệm của người nói gốc cho người xem.
- Không suy diễn tuyên bố y tế thành kết luận đã xác nhận. Chỗ nào nguồn không rõ thì viết thận trọng, không đoán thành sự thật.
- GIÁ BÁN: tuyệt đối không nhắc giá bán chính xác của sản phẩm (không con số, không đơn vị tiền, không mức giảm cụ thể, không quy đổi nhân dân tệ), kể cả khi nguồn có ghi giá. Chỉ dùng cách nói chung chung như "giá mềm", "giá dễ chịu", "giá hợp túi tiền", "đang có ưu đãi", "rẻ hơn bạn nghĩ".
- THƯƠNG HIỆU & THÔNG SỐ: tuyệt đối không nêu tên thương hiệu, nhãn hiệu, tên shop/cửa hàng, mã model, và không nêu kích thước, thể tích, dung tích, khối lượng, công suất chính xác (không con số kèm cm, mm, ml, lít, kg, gam, W, mAh…). Thay bằng từ chung chung như "sản phẩm này", "nhỏ gọn", "vừa tay", "dung tích lớn", "nhẹ", "mạnh mẽ".'''
# Exact sizes/volumes/weights/power (warned like prices; the rules ask for general wording instead).
SPEC = re.compile(r'\d[\d.,]*\s*(?:cm|mm|ml|lít|lit|kg|gam|gram|mah|inch|kw|w|l|g|m)\b',re.I)
# Always added, even to a customised template: the user asked for this to hold without exception.
STRICT = 'BẮT BUỘC (luôn áp dụng): không nêu giá bán chính xác, tên thương hiệu/nhãn hiệu/shop/mã model, kích thước, thể tích, dung tích, khối lượng, công suất chính xác của sản phẩm; chỉ dùng từ ngữ chung chung.'
PRICE = re.compile(r'(?:\d[\d.,]*\s*(?:k\b|nghìn|ngàn|nghin|ngan|triệu|trieu|tr\b|đồng|dong\b|đ\b|vnđ|vnd|tệ|nhân dân tệ|yuan|rmb|usd|\$|元|块)|[¥$￥]\s*\d)',re.I)
MAX_RULES = 20000
