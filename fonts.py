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
    'mono': ('DejaVuSansMono.ttf', 'Mono', 'Mono đều nét'),
    'mono-bold': ('DejaVuSansMono-Bold.ttf', 'MonoBold', 'Mono đậm'),
}


@lru_cache(maxsize=6)
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


def width(text, font, size):
    advances, missing = metrics(font)
    return sum(advances.get(ord(c), missing) for c in text)*size


def wrap(text, font, size, max_width):
    result = []
    for paragraph in text.split('\n'):
        line = ''
        for word in paragraph.split():
            candidate = (line+' '+word).strip()
            if width(candidate,font,size)<=max_width:
                line = candidate
                continue
            if line:
                result.append(line)
                line = ''
            for character in word:
                if line and width(line+character,font,size)>max_width:
                    result.append(line)
                    line = ''
                line += character
        result.append(line)
    return result
