"""Bundled font catalog and TrueType advance metrics for wrapping text offline."""
from functools import lru_cache
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parent
FONTS = {
    'sans': ('DejaVuSans.ttf', 'Sans', 'Sans thường'),
    'sans-bold': ('DejaVuSans-Bold.ttf', 'SansBold', 'Sans đậm'),
    'serif': ('DejaVuSerif.ttf', 'Serif', 'Serif thanh lịch'),
    'serif-bold': ('DejaVuSerif-Bold.ttf', 'SerifBold', 'Serif đậm'),
    # Vietnamese-ready fonts (SIL Open Font License, see assets/FONT_LICENSE_OFL.txt)
    'bvp': ('BeVietnamPro-Regular.ttf', 'BeVietnam', 'Be Vietnam Pro'),
    'bvp-bold': ('BeVietnamPro-Bold.ttf', 'BeVietnamBold', 'Be Vietnam Pro đậm'),
    'bvp-black': ('BeVietnamPro-Black.ttf', 'BeVietnamBlack', 'Be Vietnam Pro rất đậm'),
    'barlow': ('Barlow-Medium.ttf', 'BarlowMedium', 'Barlow'),
    'barlow-xbold': ('Barlow-ExtraBold.ttf', 'BarlowXBold', 'Barlow đậm'),
    'kanit': ('Kanit-Medium.ttf', 'KanitMedium', 'Kanit'),
    'kanit-bold': ('Kanit-Bold.ttf', 'KanitBold', 'Kanit đậm'),
    'prompt': ('Prompt-SemiBold.ttf', 'PromptSemi', 'Prompt'),
    'mitr': ('Mitr-Medium.ttf', 'MitrMedium', 'Mitr tròn'),
    'chakra': ('ChakraPetch-Bold.ttf', 'ChakraBold', 'Chakra Petch · công nghệ'),
    'anton': ('Anton-Regular.ttf', 'Anton', 'Anton · cao, nổi bật'),
    'bungee': ('Bungee-Regular.ttf', 'Bungee', 'Bungee · khối đậm'),
    'paytone': ('PaytoneOne-Regular.ttf', 'PaytoneOne', 'Paytone One · tròn đậm'),
    'coiny': ('Coiny-Regular.ttf', 'Coiny', 'Coiny · vui nhộn'),
    'bangers': ('Bangers-Regular.ttf', 'Bangers', 'Bangers · truyện tranh'),
    'lobster': ('Lobster-Regular.ttf', 'Lobster', 'Lobster · viết tay đậm'),
    'pacifico': ('Pacifico-Regular.ttf', 'Pacifico', 'Pacifico · viết tay'),
    'charm': ('Charm-Bold.ttf', 'CharmBold', 'Charm · thư pháp'),
    'sriracha': ('Sriracha-Regular.ttf', 'Sriracha', 'Sriracha · bút lông'),
    'patrick': ('PatrickHand-Regular.ttf', 'PatrickHand', 'Patrick Hand · viết tay'),
    'itim': ('Itim-Regular.ttf', 'Itim', 'Itim · dễ thương'),
    'mali': ('Mali-Bold.ttf', 'MaliBold', 'Mali · dễ thương đậm'),
    'krub': ('Krub-Bold.ttf', 'KrubBold', 'Krub · hiện đại'),
    'montserrat': ('Montserrat-ExtraBold.ttf', 'MontserratXB', 'Montserrat · hiện đại đậm'),
    'nunito': ('Nunito-Black.ttf', 'NunitoBlack', 'Nunito · tròn mềm'),
    'lexend': ('Lexend-ExtraBold.ttf', 'LexendXB', 'Lexend · dễ đọc'),
    'oswald': ('Oswald-Bold.ttf', 'OswaldBold', 'Oswald · cao gọn'),
    'baloo': ('Baloo2-ExtraBold.ttf', 'Baloo2XB', 'Baloo 2 · tròn vui'),
    'quicksand': ('Quicksand-Bold.ttf', 'QuicksandBold', 'Quicksand · nhẹ nhàng'),
    'fira': ('FiraSans-Black.ttf', 'FiraBlack', 'Fira Sans · rất đậm'),
    # kept for older templates: DejaVu Sans Mono lacks some Vietnamese letters (ẳ ế ố ở ử…)
    'mono': ('DejaVuSansMono.ttf', 'Mono', 'Mono đều nét · thiếu vài dấu'),
    'mono-bold': ('DejaVuSansMono-Bold.ttf', 'MonoBold', 'Mono đậm · thiếu vài dấu'),
}


@lru_cache(maxsize=64)
def metrics(font):
    raw = (ROOT / 'assets' / FONTS[font][0]).read_bytes()
    u16 = lambda p: struct.unpack_from('>H', raw, p)[0]
    tables = {}
    for i in range(u16(4)):
        tag, _, offset, _ = struct.unpack_from('>4sIII', raw, 12+16*i)
        tables[tag] = offset
    units = u16(tables[b'head']+18)
    count = u16(tables[b'hhea']+34)
    hmtx = tables[b'hmtx']
    cmap = tables[b'cmap']
    for i in range(u16(cmap+2)):
        _, _, offset = struct.unpack_from('>HHI', raw, cmap+4+8*i)
        at = cmap+offset
        if u16(at) == 4:
            break
    else:
        raise ValueError('Font thiếu bảng Unicode.')
    n = u16(at+6)//2
    end = at+14
    start = end+2*n+2
    delta = start+2*n
    ranges = delta+2*n
    widths = {}
    for i in range(n):
        for code in range(u16(start+2*i), u16(end+2*i)+1):
            if code == 65535:
                continue
            ro = u16(ranges+2*i)
            glyph = u16(ranges+2*i+ro+2*(code-u16(start+2*i))) if ro else code
            if glyph or not ro:
                glyph = (glyph+u16(delta+2*i))&65535
            widths[code] = u16(hmtx+4*min(glyph,count-1))/units
    return widths, u16(hmtx)/units


@lru_cache(maxsize=64)
def vertical(font):
    """(ascender, descender) of the font's hhea table, in em: where the browser puts the baseline in a line box."""
    raw = (ROOT / 'assets' / FONTS[font][0]).read_bytes()
    u16 = lambda p: struct.unpack_from('>H', raw, p)[0]
    s16 = lambda p: struct.unpack_from('>h', raw, p)[0]
    tables = {struct.unpack_from('>4s', raw, 12+16*i)[0]: struct.unpack_from('>I', raw, 12+16*i+8)[0] for i in range(u16(4))}
    units = u16(tables[b'head']+18)
    return s16(tables[b'hhea']+4)/units, abs(s16(tables[b'hhea']+6))/units


def width(text, font, size):
    advances, missing = metrics(font)
    return sum(advances.get(ord(c), missing) for c in text)*size


def wrap(text, font, size, max_width, spacing=0, letter=0):
    """Lines that fit max_width; spacing = extra width at every space between words, letter = between all letters."""
    result = []
    for paragraph in text.split('\n'):
        line = ''
        for word in paragraph.split():
            candidate = (line+' '+word).strip()
            if width(candidate,font,size)+spacing*candidate.count(' ')+letter*max(0,len(candidate)-1)<=max_width:
                line = candidate
                continue
            if line:
                result.append(line)
                line = ''
            for character in word:
                if line and width(line+character,font,size)+letter*len(line)>max_width:
                    result.append(line)
                    line = ''
                line += character
        result.append(line)
    return result


@lru_cache(maxsize=64)
def family(font):
    """The font's own full name (name table, ID 4, else 1): what libass matches for the burned-in captions."""
    raw = (ROOT / 'assets' / FONTS[font][0]).read_bytes()
    u16 = lambda p: struct.unpack_from('>H', raw, p)[0]
    for i in range(u16(4)):
        tag, _, offset, _ = struct.unpack_from('>4sIII', raw, 12+16*i)
        if tag == b'name':
            break
    else:
        return FONTS[font][1]
    count, strings = u16(offset+2), offset+u16(offset+4)
    found = {}
    for i in range(count):
        platform, encoding, _, name_id, length, at = struct.unpack_from('>HHHHHH', raw, offset+6+12*i)
        if name_id in (1, 4) and platform in (0, 3):
            try:
                found.setdefault(name_id, raw[strings+at:strings+at+length].decode('utf-16-be'))
            except UnicodeDecodeError:
                pass
    return found.get(4) or found.get(1) or FONTS[font][1]
