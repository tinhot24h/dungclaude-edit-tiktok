"""Title / body / file-name helpers shared by the dubbing queue and the "Dịch & biên tập AI" page: the same
character limits, title styles, variant picking and file-name rules everywhere."""
import re
import unicodedata


def words_for(chars):
    """About how many Vietnamese words fit in that many characters (a word is ~4.5 letters + a space)."""
    return max(1, int(chars / 5.5))


# Kiểu tiêu đề (chosen in the Tiêu đề group, saved in the template)
TITLE_STYLES = {
    'auto': 'tự chọn kiểu hợp nhất với video (câu hỏi, nỗi đau – giải pháp, lợi ích chính hoặc gây tò mò); 3 phương án dùng 3 kiểu khác nhau',
    'question': 'câu hỏi đánh trúng nhu cầu người xem, ví dụ "Da khô mùa lạnh?", "Bếp chật để đồ ở đâu?"',
    'pain': 'nỗi đau – giải pháp: nêu một phiền toái quen thuộc rồi cách sản phẩm giải quyết, ví dụ "Hết cảnh tóc rụng đầy sàn"',
    'benefit': 'lợi ích chính: nói thẳng điểm mạnh nhất của sản phẩm, ví dụ "Lau một lần sạch bóng"',
    'curious': 'gây tò mò: hé lộ một điểm bất ngờ có trong video nhưng không nói hết, ví dụ "Món đồ khiến cả nhà bất ngờ"',
}
TITLE_COUNT, BODY_COUNT = 3, 2


def slug_name(text):
    """quan-ao-nu-hottrend: lower case, no accents, words joined by '-', at most 30 characters (cut between words)."""
    text = unicodedata.normalize('NFD', str(text or '').replace('đ', 'd').replace('Đ', 'D'))
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn').lower()
    text = re.sub(r'[^a-z0-9]+', '-', text).strip('-')
    if len(text) > 30:
        cut = text[:31].rfind('-')
        text = text[:cut] if cut >= 15 else text[:30]
    return text.rstrip('-')


DANGLING = {'và', 'cho', 'của', 'với', 'để', 'là', 'thì', 'mà', 'nhưng', 'hay', 'hoặc', 'các', 'những', 'một', 'giúp', 'khi',
            'từ', 'trong', 'ở', 'tại', 'về', 'theo', 'đến', 'rất', 'càng', 'cùng', 'nên', 'vì', 'do', 'bởi', 'được', 'bị', 'sẽ', 'đã', 'đang'}


def limit_chars(text, most, sentences=False):
    """At most `most` characters (spaces included), never splitting a word: the body ends at the last full sentence
    when that keeps most of it, and a cut never ends on a linking word ("và", "cho", "của"…)."""
    text = ' '.join(str(text or '').split())
    if len(text) <= most:
        return text, False
    head = text[:most + 1]
    if sentences:
        end = max(head.rfind(p) for p in '.!?…')
        if end >= most * .6:
            return head[:end + 1].strip(), True
    space = head.rfind(' ')
    words = (head[:space] if space >= most // 2 else text[:most]).split(' ')
    while len(words) > 1 and words[-1].lower().strip(',;:–-') in DANGLING:
        words.pop()
    return ' '.join(words).rstrip(' ,;:–-'), True


def text_problems(text, most, least=0):
    """Why a title/body variant cannot be used as is: too long / too short / price or spec / ends on a linking word."""
    from ai_translate import PRICE, SPEC   # (ai_translate imports this module)
    out = []
    if not text:
        return ['trống']
    if len(text) > most:
        out.append('dài')
    if len(text) < least:
        out.append('ngắn')
    if PRICE.search(text) or SPEC.search(text):
        out.append('giá/thông số')
    if text.split(' ')[-1].lower().strip('.,;:!?…–-') in DANGLING:
        out.append('cụt')
    return out


def pick_text(variants, most, least=0, body=False):
    """The longest variant that fits; else one that is only short; else the cleanest one cut to the limit.
    Returns (text, cut, problems)."""
    clean = []
    for v in variants:
        v = '\n'.join(' '.join(line.split()) for line in str(v or '').splitlines() if line.strip()).strip('"“”')
        if not body:
            v = v.rstrip('.')
        if v and v not in clean:
            clean.append(v)
    if not clean:
        return '', False, ['trống']
    graded = [(v, text_problems(v, most, least)) for v in clean]
    for allowed in ((), ('ngắn',)):
        ok = [v for v, p in graded if set(p) <= set(allowed)]
        if ok:
            best = max(ok, key=len)
            return best, False, dict(graded)[best]
    usable = [v for v, p in graded if 'giá/thông số' not in p] or clean
    best = min(usable, key=len)
    text, cut = limit_chars(best, most, sentences=body)
    return text, cut, [p for p in text_problems(text, most, least) if p != 'dài']


def text_targets(settings):
    """Character targets for the title/body variants (short → long), all inside the limits."""
    t, lo, hi = settings['title_chars'], settings['body_min_chars'], settings['body_max_chars']
    return [max(4, round(t * f)) for f in (.6, .8, .95)], [round(lo + (hi - lo) * f) for f in (.35, .85)]
