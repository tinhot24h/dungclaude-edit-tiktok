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
    'experience': 'Trải nghiệm thực tế: kể theo trình tự dùng thử (mở hộp → dùng → cảm nhận), nói cả điểm hay lẫn lưu ý, câu ngắn tự nhiên như đang quay vlog; chỉ kể trải nghiệm mà người nói gốc đã kể, không tự bịa cảm nhận.',
    'beauty': 'Làm đẹp · chăm sóc: nhẹ nhàng, tinh tế, chú trọng cảm giác khi dùng, cách dùng và thói quen chăm sóc; tuyệt đối không cam kết hiệu quả điều trị, không dùng từ y khoa khẳng định.',
    'tech': 'Công nghệ · đồ điện tử: rõ ràng, đi thẳng vào tính năng và lợi ích khi dùng, giải thích dễ hiểu cho người không rành kỹ thuật.',
    'food': 'Ẩm thực: gợi hình gợi vị (giòn, thơm, đậm đà…), kể cách làm/cách ăn theo thứ tự, giọng hào hứng vừa phải.',
    'fashion': 'Thời trang: nói về phong cách, cách phối, chất liệu và cảm giác mặc, gợi ý dịp dùng; giọng trẻ trung, có gu.',
    'fun': 'Giải trí · hài hước: nhịp nhanh, câu ngắn, dí dỏm, có thể dùng từ trend phổ biến nhưng không thô tục, không xúc phạm.',
}
# Văn phong in full (0.29): tone, the first 3 seconds, the order of ideas, words to use / avoid and an example opening.
# Sent with the voice paragraph and the on-screen title/body; a line-by-line translation (timed to each line) only
# gets the short STYLES line above, so lines do not get longer. `titles` = title kinds "Tự chọn" picks from.
STYLE_PROFILES = {
    'review': dict(tone='như bạn bè giới thiệu món đồ hay, gần gũi, chân thật, nhịp vừa phải',
                   open='mở bằng điểm đáng chú ý nhất hoặc một câu hỏi về nhu cầu',
                   flow='giới thiệu món đồ → 2–3 điểm nổi bật kèm cách dùng → câu chốt nhẹ nhàng gợi ý nên thử',
                   use='"điểm mình thích là", "dùng rất tiện", "nhìn là thấy", "đáng tiền"', avoid='lời quảng cáo sáo rỗng, "tốt nhất thị trường", "cam kết 100%"',
                   example='Món này nhỏ thôi mà giải quyết được cả đống phiền toái nè.', titles='lợi ích chính, câu hỏi hoặc gây tò mò'),
    'household': dict(tone='như người trong nhà mách nhau mẹo hay, ấm áp, thực tế',
                      open='mở bằng một tình huống quen thuộc trong nhà (bếp bừa, đồ khó cất, giặt giũ mất thời gian…)',
                      flow='phiền toái quen thuộc → món đồ xử lý thế nào → cảm giác gọn gàng, sạch sẽ, đỡ mất thời gian',
                      use='"gọn gàng", "sạch bong", "đỡ tốn công", "cả nhà đều dùng được", "an toàn"', avoid='phóng đại công dụng, từ kỹ thuật khó hiểu',
                      example='Ai hay phải dọn bếp sau mỗi bữa thì xem cái này nha.', titles='nỗi đau – giải pháp hoặc lợi ích chính'),
    'experience': dict(tone='như đang quay vlog dùng thử, tự nhiên, có cảm xúc nhưng trung thực',
                       open='mở bằng khoảnh khắc mở hộp hoặc lần đầu cầm lên',
                       flow='mở hộp → dùng thử từng bước → cảm nhận thật, cả điểm hay lẫn lưu ý → nhận xét chung',
                       use='"cầm lên thấy", "thử luôn nè", "điểm cộng là", "lưu ý nhỏ"', avoid='bịa trải nghiệm hay cảm nhận mà người nói gốc không kể',
                       example='Mở hộp ra thử luôn cho mọi người xem nè.', titles='gây tò mò hoặc câu hỏi'),
    'news': dict(tone='trung tính, rõ ràng, đáng tin, không cảm thán',
                 open='mở bằng thông tin chính (ai, cái gì, ở đâu)',
                 flow='thông tin chính → chi tiết quan trọng → bối cảnh hoặc diễn biến tiếp theo',
                 use='"theo", "cho biết", "hiện", "dự kiến"', avoid='từ cảm thán, suy đoán thành sự thật, giọng bán hàng',
                 example='Một sản phẩm mới vừa được giới thiệu với điểm khác biệt đáng chú ý.', titles='lợi ích chính hoặc câu hỏi; KHÔNG dùng kiểu nỗi đau – giải pháp'),
    'tips': dict(tone='như người chia sẻ mẹo, rõ ràng, dứt khoát, dễ làm theo',
                 open='mở bằng vấn đề người xem hay gặp',
                 flow='vấn đề → các bước ngắn theo thứ tự → kết quả (chỉ trong phạm vi nguồn)',
                 use='"mẹo nhỏ là", "chỉ cần", "bước một… bước hai", "làm vậy thì"', avoid='hứa kết quả nguồn không nói, bước rườm rà',
                 example='Đồ hay bị rối thì thử cách này, mất chưa tới một phút.', titles='nỗi đau – giải pháp hoặc câu hỏi'),
    'intro': dict(tone='mạch lạc, chuyên nghiệp mà vẫn thân thiện',
                  open='mở bằng sản phẩm là gì và dành cho ai',
                  flow='sản phẩm là gì → 2–3 lợi ích chính → hợp với ai, dùng khi nào',
                  use='"được thiết kế để", "phù hợp cho", "giúp bạn"', avoid='cường điệu, so sánh hạ thấp sản phẩm khác',
                  example='Đây là món đồ dành cho ai muốn góc bếp gọn gàng hơn.', titles='lợi ích chính'),
    'beauty': dict(tone='nhẹ nhàng, tinh tế, dịu dàng, chú trọng cảm giác',
                   open='mở bằng một nỗi lo làm đẹp quen thuộc hoặc cảm giác khi dùng',
                   flow='nỗi lo hoặc nhu cầu → kết cấu, mùi, cảm giác khi dùng → cách dùng trong thói quen chăm sóc',
                   use='"thấm nhanh", "mềm mịn", "nhẹ mặt", "dễ chịu", "chăm sóc mỗi ngày"', avoid='cam kết hiệu quả điều trị, từ y khoa khẳng định (trị dứt, chữa khỏi)',
                   example='Da mùa này hay khô căng thì nghe mình nói chút nha.', titles='câu hỏi hoặc lợi ích chính'),
    'tech': dict(tone='rõ ràng, gọn, tự tin, dễ hiểu cho người không rành kỹ thuật',
                 open='mở bằng tính năng gây ấn tượng nhất',
                 flow='tính năng nổi bật → dùng trong tình huống thật thế nào → ai nên dùng',
                 use='"kết nối nhanh", "dùng mượt", "pin trâu", "thao tác đơn giản"', avoid='thuật ngữ khó, đọc cấu hình',
                 example='Cái này bấm một cái là kết nối xong, khỏi cài đặt gì.', titles='lợi ích chính hoặc gây tò mò'),
    'food': dict(tone='hào hứng vừa phải, gợi hình gợi vị',
                 open='mở bằng hình ảnh hoặc mùi vị hấp dẫn nhất',
                 flow='món gì → cách làm hoặc cách ăn theo thứ tự → cảm nhận vị',
                 use='"giòn rụm", "thơm lừng", "đậm đà", "béo ngậy", "chấm là ghiền"', avoid='so sánh chê món khác, từ thô',
                 example='Nhìn lớp vỏ giòn rụm này là đủ biết ngon rồi.', titles='gây tò mò hoặc lợi ích chính'),
    'fashion': dict(tone='trẻ trung, có gu, tự tin',
                    open='mở bằng phong cách hoặc dịp mặc',
                    flow='phong cách → chất liệu và cảm giác mặc → cách phối, dịp dùng',
                    use='"lên dáng", "dễ phối", "mặc mát", "tôn dáng", "đi đâu cũng hợp"', avoid='chê vóc dáng người mặc, từ khó hiểu',
                    example='Một chiếc váy mà đi biển hay đi cà phê đều xinh.', titles='lợi ích chính hoặc câu hỏi'),
    'fun': dict(tone='dí dỏm, nhịp nhanh, câu ngắn, có thể bắt trend nhẹ',
                open='mở bằng một câu bất ngờ hoặc câu đùa ngắn',
                flow='tình huống hài → món đồ xuất hiện → câu chốt bất ngờ',
                use='từ trend phổ biến, so sánh vui, câu cảm thán ngắn', avoid='thô tục, xúc phạm, châm biếm người khác',
                example='Tưởng đồ chơi, ai ngờ dùng thật mới thấy hay.', titles='gây tò mò hoặc câu hỏi'),
}
ENERGY = {'low': 'nhẹ nhàng, điềm tĩnh, ít câu cảm thán', 'mid': 'tự nhiên, vừa phải', 'high': 'hào hứng, nhiều năng lượng, câu ngắn dồn dập (vẫn không phóng đại sự thật)'}
ENERGY_LABELS = {'low': 'Nhẹ nhàng', 'mid': 'Vừa phải', 'high': 'Hào hứng'}


def style_rules(style, energy='mid', full=True):
    """The "Văn phong" part of the rules: full profile for written texts, one line for timed line translation."""
    head = STYLES[style] + ' Mức hào hứng: ' + ENERGY.get(energy, ENERGY['mid']) + '.'
    if not full:
        return head
    p = STYLE_PROFILES[style]
    return (head + f'\n  · Giọng: {p["tone"]}.\n  · 3 giây đầu: {p["open"]} (câu đầu phải giữ chân người xem).\n  · Trình tự ý: {p["flow"]}.'
            f'\n  · Nên dùng: {p["use"]}. Tránh: {p["avoid"]}.\n  · Câu mở mẫu (chỉ để cảm giọng, không chép): {p["example"]}')


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
