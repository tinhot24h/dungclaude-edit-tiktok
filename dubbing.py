"""Automatic Chinese → Vietnamese dubbing.

01 Nhận diện  OpenAI Whisper (whisper-1) → Chinese SRT with timestamps (or an SRT the user already has)
02 Dịch       OpenAI → natural Vietnamese, each line sized to the time it has on screen
03 Tách âm    background kept by: Demucs (if installed), centre-channel cancel, ducking under speech, or removed
04 Lồng tiếng ai33.pro TTS per sentence group → fitted (gentle speed-up) and placed at the original timestamps
05 Xuất       MP4 H.264 + AAC, Vietnamese voice, optional Vietnamese SRT (separate file or soft track; never burned into the picture)

Jobs run one at a time in a worker thread. Their state (segments, translations, ai33 task ids) is saved in
.local/dub/<id>/job.json so a restart never re-buys a TTS task; API keys are only held in memory.
"""
import json
import math
import random
import os
import re
import shutil
import socket
import subprocess
import threading
import time
import uuid
import wave
from pathlib import Path
from urllib import request, error
import ai33_audio
import ai_translate
import audio_files
import output_folder
import secrets_store
from media_engine import tempo as tempo_filter

OPENAI = os.environ.get('REVIEW_OPENAI_BASE', 'https://api.openai.com/v1/').rstrip('/') + '/'
STEPS = ('asr', 'translate', 'separate', 'tts', 'mix', 'export')
WEIGHTS = dict(asr=15, translate=10, separate=15, tts=40, mix=10, export=10)
# Output frame for the dubbed video; 'source' keeps the original size (even-rounded).
CANVAS = {'source': None, '9:16': (1080, 1920), '1:1': (1080, 1080), '4:5': (1080, 1350), '16:9': (1920, 1080)}
BACKGROUND = ('duck', 'center', 'demucs', 'remove', 'keep')
SUBTITLES = ('none', 'file', 'soft')
VOICE_RATE = 24000
MAX_LINES = 600
DEFAULTS = dict(language='zh', model=ai_translate.DEFAULT_MODEL, rate=4.2, pronoun='neutral', notes='', no_price=True,
                voice_id='', voice_speed=1.0, dictionary_id=None, max_tempo=1.3, background='duck', duck_level=12,
                background_volume=100, voice_volume=100, subtitles='file', loudness='tiktok', review=False, encoder='cpu', instructions='', mode='paragraph', align='auto', style='review',
                frame_canvas='source', frame_fit='cover', frame_zoom=100, frame_x=0, frame_y=0, frame_rotate=0, frame_flip='none', trim_start=0, trim_end=0,
                overlay=False, overlay_ids=[], overlay_count=1, overlay_blend='screen', overlay_opacity=60, overlay_timing='loop')
PRONOUNS = {'neutral': 'xưng hô trung tính, hạn chế đại từ', 'ban': 'gọi người xem là "bạn"', 'minh-ban': 'người nói xưng "mình", gọi người xem là "bạn"'}


class DubError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class Cancelled(Exception):
    pass


# ---------------------------------------------------------------- options and keys

def options(raw):
    raw = raw if isinstance(raw, dict) else {}
    out = dict(DEFAULTS)
    def num(key, lo, hi):
        v = raw.get(key, DEFAULTS[key])
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
            raise DubError('Thông số không hợp lệ: ' + key)
        out[key] = float(v)
    for key, lo, hi in (('frame_zoom', 25, 400), ('frame_x', -100, 100), ('frame_y', -100, 100), ('frame_rotate', -180, 180), ('overlay_opacity', 0, 100), ('trim_start', 0, 120), ('trim_end', 0, 120), ('rate', 2.5, 7), ('voice_speed', .5, 1.5), ('max_tempo', 1, 1.6), ('duck_level', 0, 100),
                        ('background_volume', 0, 200), ('voice_volume', 0, 300)):
        num(key, lo, hi)
    if raw.get('subtitles') == 'burn':  # burned-in subtitles were removed; old saved settings get the .srt file instead
        raw = dict(raw, subtitles='file')
    for key, allowed in (('language', ('zh', 'auto')), ('background', BACKGROUND), ('subtitles', SUBTITLES),
                         ('loudness', ('off', 'tiktok')), ('pronoun', tuple(PRONOUNS)), ('mode', ('paragraph', 'lines')), ('align', ('auto', 'voice', 'video')), ('style', tuple(ai_translate.STYLES)), ('frame_canvas', tuple(CANVAS)), ('frame_fit', ('cover', 'contain', 'blur')),
                         ('frame_flip', ('none', 'h', 'v', 'hv')), ('overlay_blend', ('normal', 'screen', 'key')), ('overlay_timing', ('loop', 'sequence', 'random'))):
        v = raw.get(key, DEFAULTS[key])
        if v not in allowed:
            raise DubError('Thông số không hợp lệ: ' + key)
        out[key] = v
    ids = raw.get('overlay_ids', [])
    if not isinstance(ids, list) or len(ids) > 500 or not all(isinstance(i, str) and re.fullmatch('[a-f0-9]{32}', i) for i in ids):
        raise DubError('Danh sách overlay không hợp lệ.')
    out['overlay_ids'] = ids
    count = raw.get('overlay_count', 1)
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 3:
        raise DubError('Số overlay mỗi video phải từ 1 đến 3.')
    out['overlay_count'] = count
    for key in ('no_price', 'review', 'overlay'):
        v = raw.get(key, DEFAULTS[key])
        if not isinstance(v, bool):
            raise DubError('Thông số không hợp lệ: ' + key)
        out[key] = v
    model = raw.get('model') or DEFAULTS['model']
    if not isinstance(model, str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._:-]{0,99}', model):
        raise DubError('Tên model OpenAI không hợp lệ.')
    out['model'] = model
    notes = raw.get('notes', '')
    if not isinstance(notes, str) or len(notes) > 2000:
        raise DubError('Ghi chú cho người dịch tối đa 2.000 ký tự.')
    out['notes'] = notes.strip()
    rules = raw.get('instructions', '')
    if not isinstance(rules, str) or len(rules) > ai_translate.MAX_RULES:
        raise DubError('Mẫu câu lệnh quá dài.')
    out['instructions'] = rules.strip()
    voice = raw.get('voice_id', '')
    if voice and (not isinstance(voice, str) or len(voice) > 500 or not re.fullmatch(ai33_audio.VOICE, voice)):
        raise DubError('voice_id cần prefix nhà cung cấp, ví dụ edge_vi-VN-HoaiMyNeural.')
    out['voice_id'] = voice or ''
    dictionary = raw.get('dictionary_id')
    if dictionary not in (None, ''):
        if isinstance(dictionary, bool) or not isinstance(dictionary, int) or dictionary < 1:
            raise DubError('ID từ điển phát âm không hợp lệ.')
        out['dictionary_id'] = dictionary
    else:
        out['dictionary_id'] = None
    encoder = raw.get('encoder', 'cpu')
    if not isinstance(encoder, str) or encoder not in ('cpu', 'h264_nvenc', 'h264_qsv', 'h264_amf', 'h264_videotoolbox'):
        raise DubError('Bộ mã hóa không hợp lệ.')
    out['encoder'] = encoder
    return out


def check_key(value, label):
    if not isinstance(value, str) or not value or len(value) > 1024 or any(ord(c) < 33 or ord(c) > 126 for c in value):
        raise DubError(f'{label} API key có định dạng không hợp lệ.')
    return value


def openai_key(raw):
    key = (raw or {}).get('openai_key') or secrets_store.get('openai') or os.environ.get('REVIEW_OPENAI_KEY') or os.environ.get('OPENAI_API_KEY')
    return check_key(key, 'OpenAI') if key else ''


def ai33_key(raw):
    key = (raw or {}).get('ai33_key') or secrets_store.get('ai33') or os.environ.get('REVIEW_AI33_KEY') or os.environ.get('AI33_API_KEY')
    return check_key(key, 'ai33.pro') if key else ''


def demucs_command():
    """Demucs (optional, `pip install demucs`) gives real AI vocal separation; otherwise FFmpeg modes are used."""
    found = shutil.which('demucs')
    return [found] if found else None


# ---------------------------------------------------------------- SRT

def stamp(t):
    t = max(0, t)
    ms = int(round(t * 1000))
    return f'{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}'


def parse_srt(text):
    if not isinstance(text, str) or len(text) > 2_000_000:
        raise DubError('File SRT không hợp lệ.')
    rows = []
    pattern = re.compile(r'(\d+):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d+):(\d{2}):(\d{2})[,.](\d{1,3})')
    for block in re.split(r'\n\s*\n', text.replace('\r', '').strip()):
        lines = block.strip().split('\n')
        for i, line in enumerate(lines):
            m = pattern.search(line)
            if m:
                g = [int(x) for x in m.groups()]
                start = g[0] * 3600 + g[1] * 60 + g[2] + int(m[4].ljust(3, '0')) / 1000
                end = g[4] * 3600 + g[5] * 60 + g[6] + int(m[8].ljust(3, '0')) / 1000
                body = ' '.join(' '.join(lines[i + 1:]).split())
                if body and end > start:
                    rows.append(dict(start=round(start, 3), end=round(end, 3), zh=body))
                break
    if not rows:
        raise DubError('Không đọc được dòng phụ đề nào trong file SRT.')
    if len(rows) > MAX_LINES:
        raise DubError(f'Tối đa {MAX_LINES} dòng phụ đề mỗi video.')
    return sorted(rows, key=lambda r: r['start'])


def to_srt(segments, key):
    out = []
    n = 0
    for s in segments:
        text = (s.get(key) or '').strip()
        if text:
            n += 1
            out.append(f'{n}\n{stamp(s["start"])} --> {stamp(s["end"])}\n{text}\n')
    return '\n'.join(out)


def syllables(text):
    return len(re.findall(r'[^\s.,!?;:…"“”()\-–—]+', text or ''))


def budget(segment, rate):
    return max(2, int((segment['end'] - segment['start']) * rate))


# ---------------------------------------------------------------- HTTP helpers (OpenAI)

def multipart(fields, file_field, filename, data, mime):
    boundary = 'ReviewStudio' + uuid.uuid4().hex
    parts = []
    for name, value in fields:
        parts += [f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode(), str(value).encode(), b'\r\n']
    parts += [f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'.encode(), data, b'\r\n',
              f'--{boundary}--\r\n'.encode()]
    return b''.join(parts), 'multipart/form-data; boundary=' + boundary


def openai_call(path, key, body, content_type, timeout=300):
    req = request.Request(OPENAI + path, data=body, headers={'Authorization': 'Bearer ' + key, 'Content-Type': content_type}, method='POST')
    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw = response.read(16 * 1024 * 1024)
        return json.loads(raw)
    except error.HTTPError as exc:
        messages = {401: 'OpenAI API key không hợp lệ hoặc đã hết hiệu lực.', 403: 'OpenAI từ chối key hoặc quyền dùng model.',
                    404: 'OpenAI không tìm thấy model. Kiểm tra tên model.', 413: 'File âm thanh quá lớn cho OpenAI (tối đa 25 MB).',
                    429: 'OpenAI báo hết hạn mức hoặc quá nhiều yêu cầu. Kiểm tra quota rồi bấm Tiếp tục.',
                    400: 'OpenAI không chấp nhận yêu cầu. Kiểm tra model và file âm thanh.'}
        raise DubError(messages.get(exc.code, f'OpenAI đang lỗi (HTTP {exc.code}). Thử lại sau.'), 502) from None
    except (error.URLError, socket.timeout, TimeoutError):
        raise DubError('Không kết nối được api.openai.com hoặc hết thời gian chờ. Kiểm tra mạng rồi bấm Tiếp tục.', 504) from None
    except ValueError:
        raise DubError('Không đọc được phản hồi OpenAI.', 502) from None


def transcribe_request(path, key, language):
    """OpenAI speech-to-text with segment timestamps."""
    fields = [('model', 'whisper-1'), ('response_format', 'verbose_json'), ('timestamp_granularities[]', 'segment')]
    if language == 'zh':
        fields += [('language', 'zh'), ('prompt', '以下是普通话的句子，使用简体中文和标点符号。')]
    body, content_type = multipart(fields, 'file', 'audio.mp3', Path(path).read_bytes(), 'audio/mpeg')
    return openai_call('audio/transcriptions', key, body, content_type, timeout=600)


TRANSLATE_RULES = '''Bạn là biên dịch viên lồng tiếng video ngắn, dịch lời thoại tiếng Trung sang tiếng Việt để đọc thành giọng nói khớp với hình.
- Dịch tự nhiên, khẩu ngữ, dễ nghe như người Việt nói; giữ đúng nghĩa, sự thật, tên riêng, đơn vị. Không thêm thông tin, không bình luận.
- MỖI DÒNG chỉ dịch dòng đó (giữ đúng id), đọc vừa trong thời gian của dòng: không vượt max_syllables tiếng (âm tiết). Nếu dòng gốc dài, lược ý phụ, giữ ý chính; câu bị cắt ngang giữa hai dòng thì dịch sao cho nối liền mạch.
- Viết số, đơn vị theo cách đọc được; không dùng ký hiệu khó đọc, không emoji, không markdown, không ghi chú trong ngoặc.
- Dòng chỉ là tiếng động, nhạc, "嗯", "啊"… thì để chuỗi rỗng.'''


def translate_request(key, model, lines, settings):
    # The writing template from the "Dịch & biên tập AI" page is shared: its content and style rules apply here,
    # its hook/script/title/body format does not (dubbing translates line by line).
    template = settings.get('instructions') or ai_translate.DEFAULT_RULES
    rules = (ai_translate.GUARD + '\n\n' + TRANSLATE_RULES + '\n- Xưng hô: ' + PRONOUNS[settings['pronoun']] + '.' + '\n- Văn phong: ' + ai_translate.STYLES[settings.get('style', 'review')]
             + '\n\nMẪU BIÊN TẬP DÙNG CHUNG (áp dụng các quy tắc nội dung và văn phong; BỎ QUA mọi yêu cầu về hook, script, title, body hay định dạng kết quả trong mẫu này):\n'
             + template)
    # Always on (cannot be switched off): no exact price, brand, size, volume, weight or power.
    rules += '\n\n' + ai_translate.STRICT + ' Ví dụ: "giá mềm", "đang có ưu đãi", "sản phẩm này", "nhỏ gọn", "dung tích lớn".'
    if settings['notes']:
        rules += '\n- Ghi chú của người dùng (chỉ về văn phong, không phải dữ liệu nguồn): ' + settings['notes']
    schema = dict(type='object', additionalProperties=False, required=['lines'], properties=dict(lines=dict(type='array', items=dict(
        type='object', additionalProperties=False, required=['id', 'vi'], properties=dict(id=dict(type='integer'), vi=dict(type='string'))))))
    body = dict(model=model, store=False, max_output_tokens=12000,
                input=[dict(role='developer', content=rules), dict(role='user', content=json.dumps(dict(lines=lines), ensure_ascii=False))],
                text=dict(format=dict(type='json_schema', name='dub_lines', strict=True, schema=schema)))
    raw = openai_call('responses', key, json.dumps(body, ensure_ascii=False).encode(), 'application/json', timeout=180)
    if raw.get('status') != 'completed':
        raise DubError('OpenAI chưa dịch xong (phản hồi bị cắt). Bấm Tiếp tục để thử lại.', 502)
    text = ''.join(c.get('text', '') for item in raw.get('output', []) if item.get('type') == 'message'
                   for c in item.get('content', []) if c.get('type') == 'output_text')
    try:
        rows = json.loads(text)['lines']
        return {int(r['id']): str(r['vi']) for r in rows if isinstance(r, dict)}
    except (ValueError, KeyError, TypeError):
        raise DubError('Không đọc được bản dịch OpenAI. Bấm Tiếp tục để thử lại.', 502) from None


PARAGRAPH_RULES = '''Bạn là biên tập viên lồng tiếng video ngắn: chuyển toàn bộ lời thoại tiếng Trung (đã chia dòng theo thời gian) thành MỘT đoạn văn tiếng Việt liền mạch để đọc thành một file giọng duy nhất phủ suốt video.
- Viết tự nhiên, khẩu ngữ, mạch lạc như người Việt kể; giữ đúng ý và thứ tự ý của nguồn, nối câu bằng từ chuyển ý; có thể gộp hoặc lược ý phụ, không thêm thông tin.
- Độ dài: không vượt max_syllables tiếng (âm tiết) để đọc vừa thời gian seconds; ưu tiên giữ ý chính khi phải rút gọn.
- Chia câu rõ ràng bằng dấu chấm/phẩy để giọng đọc ngắt nghỉ tự nhiên; không xuống dòng, không đánh số, không markdown, không emoji, không chú thích trong ngoặc; số và đơn vị viết theo cách đọc được.'''


def paragraph_request(key, model, segments, seconds, limit, settings):
    """Whole video → one natural Vietnamese paragraph (one ai33 file)."""
    template = settings.get('instructions') or ai_translate.DEFAULT_RULES
    rules = (ai_translate.GUARD + '\n\n' + PARAGRAPH_RULES + '\n- Xưng hô: ' + PRONOUNS[settings['pronoun']] + '.' + '\n- Văn phong: ' + ai_translate.STYLES[settings.get('style', 'review')]
             + '\n\nMẪU BIÊN TẬP DÙNG CHUNG (áp dụng các quy tắc nội dung và văn phong; BỎ QUA mọi yêu cầu về hook, script, title, body hay định dạng kết quả trong mẫu này):\n'
             + template)
    # Always on (cannot be switched off): no exact price, brand, size, volume, weight or power.
    rules += '\n\n' + ai_translate.STRICT + ' Ví dụ: "giá mềm", "đang có ưu đãi", "sản phẩm này", "nhỏ gọn", "dung tích lớn".'
    if settings['notes']:
        rules += '\n- Ghi chú của người dùng (chỉ về văn phong, không phải dữ liệu nguồn): ' + settings['notes']
    data = dict(seconds=round(seconds, 1), max_syllables=limit, lines=[dict(start=round(s['start'], 1), end=round(s['end'], 1), zh=s['zh']) for s in segments])
    schema = dict(type='object', additionalProperties=False, required=['text'], properties=dict(text=dict(type='string')))
    body = dict(model=model, store=False, max_output_tokens=12000,
                input=[dict(role='developer', content=rules), dict(role='user', content=json.dumps(data, ensure_ascii=False))],
                text=dict(format=dict(type='json_schema', name='dub_paragraph', strict=True, schema=schema)))
    raw = openai_call('responses', key, json.dumps(body, ensure_ascii=False).encode(), 'application/json', timeout=180)
    if raw.get('status') != 'completed':
        raise DubError('OpenAI chưa dịch xong (phản hồi bị cắt). Bấm Tiếp tục để thử lại.', 502)
    text = ''.join(c.get('text', '') for item in raw.get('output', []) if item.get('type') == 'message'
                   for c in item.get('content', []) if c.get('type') == 'output_text')
    try:
        return ' '.join(str(json.loads(text)['text']).split())
    except (ValueError, KeyError, TypeError):
        raise DubError('Không đọc được bản dịch OpenAI. Bấm Tiếp tục để thử lại.', 502) from None


def silences(path):
    """Mid-points (seconds) of the pauses in a voice file, for placing subtitle changes."""
    try:
        out = subprocess.run(['ffmpeg', '-hide_banner', '-nostdin', '-i', str(path), '-af', 'silencedetect=noise=-35dB:d=0.22', '-f', 'null', '-'],
                             capture_output=True, text=True, timeout=120).stderr
    except (OSError, subprocess.SubprocessError):
        return []
    starts = [float(x) for x in re.findall(r'silence_start: (-?[\d.]+)', out)]
    ends = [float(x) for x in re.findall(r'silence_end: ([\d.]+)', out)]
    return [round((a + b) / 2, 3) for a, b in zip(starts, ends) if b > a]


def sentence_lines(text, start, seconds, pauses=()):
    """Subtitle lines for the paragraph: sentences spread over the voice by length; each boundary moves to the
    nearest pause (within 1.2 s) so the text changes when the voice actually breaks."""
    parts = [p.strip() for p in re.split(r'(?<=[.!?…])\s+', text) if p.strip()]
    out = []
    pieces = []
    for p in parts:
        # long sentences are split at commas so each subtitle stays readable
        while len(p) > 90 and ',' in p[30:]:
            cut = p.index(',', 30) + 1
            pieces.append(p[:cut].strip())
            p = p[cut:].strip()
        pieces.append(p)
    total = sum(len(p) for p in pieces) or 1
    cuts, done = [], 0
    for p in pieces[:-1]:
        done += len(p)
        guess = seconds * done / total
        low = (cuts[-1] if cuts else 0) + .3
        near = [t for t in pauses if abs(t - guess) <= 1.2 and low < t < seconds - .3]
        cuts.append(min(near, key=lambda t: abs(t - guess)) if near else max(low, guess))
    edges = [0, *cuts, seconds]
    for i, p in enumerate(pieces):
        out.append(dict(start=round(start + edges[i], 3), end=round(start + edges[i + 1], 3), vi=p))
    return out


def paragraph_window(job):
    """Where the single voice file goes: from the first spoken line to the end of the video."""
    first = min((s['start'] for s in job['segments']), default=0)
    return first, max(1.0, job['duration'] - first)


# ---------------------------------------------------------------- media helpers

def run(cmd, cancel=None, timeout=7200, cwd=None):
    """FFmpeg/Demucs with cancel support; returns stderr tail on failure."""
    with subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE) as proc:
        deadline = time.monotonic() + timeout
        while True:
            try:
                _, err = proc.communicate(timeout=.5)
                break
            except subprocess.TimeoutExpired:
                if (cancel and cancel.is_set()) or time.monotonic() > deadline:
                    proc.kill()
                    proc.communicate()
                    if cancel and cancel.is_set():
                        raise Cancelled()
                    raise DubError('Xử lý quá lâu, đã dừng.')
        if proc.returncode:
            raise DubError('FFmpeg xử lý lỗi: ' + err.decode('utf-8', 'replace').strip()[-300:])


def probe(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_type,codec_name,width,height,channels,pix_fmt',
                          '-of', 'json', str(path)], capture_output=True, text=True, timeout=30)
    data = json.loads(out.stdout or '{}')
    streams = data.get('streams', [])
    video = next((s for s in streams if s.get('codec_type') == 'video'), {})
    audio = next((s for s in streams if s.get('codec_type') == 'audio'), None)
    return dict(duration=float(data.get('format', {}).get('duration', 0) or 0), video=video, audio=audio)


def mix_voice(groups, folder, duration):
    """Write voice.wav (mono 24 kHz) with every fitted clip copied in at its start time."""
    total = int(math.ceil(duration * VOICE_RATE)) * 2
    buffer = bytearray(total)
    for g in groups:
        if not g.get('raw'):
            continue
        data = (folder / g['raw']).read_bytes()
        at = int(g.get('place', g['start']) * VOICE_RATE) * 2
        data = data[:max(0, total - at)]
        buffer[at:at + len(data)] = data
    with wave.open(str(folder / 'voice.wav'), 'wb') as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(VOICE_RATE)
        out.writeframes(bytes(buffer))
    return folder / 'voice.wav'


def group_segments(segments, gap=.35, longest=14):
    """Join neighbouring lines into natural sentences for TTS (fewer tasks, smoother intonation)."""
    groups = []
    for i, s in enumerate(segments):
        text = (s.get('vi') or '').strip()
        if not text:
            continue
        last = groups[-1] if groups else None
        if last and s['start'] - last['end'] <= gap and s['end'] - last['start'] <= longest and not re.search(r'[.!?…]$', last['text']):
            last['end'] = s['end']
            last['text'] += ' ' + text
            last['lines'].append(i)
        else:
            groups.append(dict(start=s['start'], end=s['end'], text=text, lines=[i]))
    return groups


def fit(groups, duration, max_tempo):
    """Speed each clip up (at most max_tempo) so it ends before the next one starts; report what still overflows."""
    warnings = []
    for k, g in enumerate(groups):
        if not g.get('clip_seconds'):
            continue
        slot = (groups[k + 1]['start'] if k + 1 < len(groups) else duration) - g['start'] - .04
        slot = max(.2, slot)
        need = g['clip_seconds'] / slot
        g['tempo'] = round(min(max(1.0, need), max_tempo), 3)
        g['overflow'] = round(max(0, g['clip_seconds'] / g['tempo'] - slot), 2)
        if g['overflow'] > .05:
            warnings.append(f'Câu lúc {stamp(g["start"])[:8]} dài hơn chỗ trống {g["overflow"]}s dù đã đọc nhanh {g["tempo"]}×; phần cuối được làm nhỏ dần. Rút gọn câu dịch để khớp hơn.')
    return warnings


def frame_size(settings, video):
    w, h = int(video.get('width') or 720), int(video.get('height') or 1280)
    return CANVAS.get(settings.get('frame_canvas', 'source')) or (w // 2 * 2, h // 2 * 2)


def frame_identity(settings):
    return (settings.get('frame_canvas', 'source') == 'source' and settings.get('frame_zoom', 100) == 100 and not settings.get('frame_x')
            and not settings.get('frame_y') and not settings.get('frame_rotate') and settings.get('frame_flip', 'none') == 'none')


def frame_graph(settings, video, before, after):
    """[0:v:0] → [vout]: flip, fit into a box of canvas×zoom (cover crops, contain/blur pad), rotate the box about its
    centre, place it at the offset on black or a blurred copy. Same order as the CSS preview, so both match."""
    W, H = frame_size(settings, video)
    tail = ','.join(after + ['format=yuv420p'])
    pre = list(before) + ['hflip'] * ('h' in settings['frame_flip']) + ['vflip'] * ('v' in settings['frame_flip'])
    if frame_identity(settings):
        return ['[0:v:0]' + ','.join(pre + [tail]) + '[vout]'], (W, H)
    z = settings['frame_zoom'] / 100
    bw, bh = max(2, round(W * z / 2) * 2), max(2, round(H * z / 2) * 2)
    fit = settings['frame_fit']
    box = (f'scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh}' if fit == 'cover' else
           f'scale={bw}:{bh}:force_original_aspect_ratio=decrease,format=rgba,pad={bw}:{bh}:(ow-iw)/2:(oh-ih)/2:color=black@0')
    turn = math.radians(settings['frame_rotate'])
    if turn:
        box += f',format=rgba,rotate={turn:.9f}:ow=rotw({turn:.9f}):oh=roth({turn:.9f}):c=none'
    lines = ['[0:v:0]' + ','.join(pre + ['setsar=1']) + (',split=2[fgsrc][bgsrc]' if fit == 'blur' else '[fgsrc]'), f'[fgsrc]{box}[fg]']
    lines.append(f'[bgsrc]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=24:2,setsar=1[bg]' if fit == 'blur'
                 else f'color=c=black:s={W}x{H}:r=30,setsar=1[bg]')
    dx, dy = round(settings['frame_x'] * W / 200), round(settings['frame_y'] * H / 200)
    lines.append(f'[bg][fg]overlay=x=(main_w-overlay_w)/2+({dx}):y=(main_h-overlay_h)/2+({dy}):shortest=1:format=auto,{tail}[vout]')
    return lines, (W, H)


OVERLAY_TYPES = ('.mp4', '.mov', '.webm', '.mkv', '.m4v', '.gif', '.png', '.webp', '.jpg', '.jpeg')


def overlay_fit(W, H):
    return f'fps=30,scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1'


def overlay_chain(source, item, W, H, settings, base, duration):
    """Graph lines putting an overlay stream (`source`: an input like [3:v] or a joined sequence label) on top of
    [base]; returns (lines, new label). Longer than the video → cut to the video; shorter → looped or joined
    (decided by the inputs). normal/key: alpha overlay (key removes a green background) · screen: blend for effects on black."""
    op = settings['overlay_opacity'] / 100
    k = item['k']
    random_time = settings['overlay_timing'] == 'random'
    chain = f'{source}{overlay_fit(W, H)}' + ('' if random_time else f',trim=duration={duration:.3f},setpts=PTS-STARTPTS')
    if settings['overlay_blend'] == 'screen':
        if random_time:
            chain += f",tpad=start_duration={item['start']:.3f}:stop_duration={duration + 5:.3f}:color=black"
        return [chain + f',format=gbrp[ov{k}]', f'[{base}]format=gbrp[bk{k}]',
                f'[bk{k}][ov{k}]blend=all_mode=screen:all_opacity={op:.3f}:shortest=1[os{k}]'], f'os{k}'
    if settings['overlay_blend'] == 'key':
        chain += ',colorkey=0x00FF00:0.30:0.10'
    chain += f',format=rgba,colorchannelmixer=aa={op:.3f}'
    if random_time:
        chain += f",setpts=PTS-STARTPTS+{item['start']:.3f}/TB"
    return [chain + f'[ov{k}]', f'[{base}][ov{k}]overlay=0:0:eof_action=pass:format=auto' + ('' if random_time else ':shortest=1') + f'[os{k}]'], f'os{k}'


# ---------------------------------------------------------------- job store and worker

class Store:
    def __init__(self, data_dir, settings_path, video_dir, audio_dir, encoder_args):
        self.root = Path(data_dir) / 'dub'
        self.root.mkdir(parents=True, exist_ok=True)
        self.settings_path = settings_path
        self.video_dir = Path(video_dir)
        self.audio_dir = Path(audio_dir)
        self.encoder_args = encoder_args
        self.overlay_dir = Path(data_dir) / 'overlays'
        self.overlay_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.queue = []
        self.keys = {}
        self.cancels = {}
        self.live = {}
        self.wake = threading.Event()
        threading.Thread(target=self.worker, daemon=True).start()

    # -- persistence
    def path(self, key):
        if not isinstance(key, str) or not re.fullmatch('[a-f0-9]{32}', key):
            raise DubError('Mã tác vụ lồng tiếng không hợp lệ.')
        return self.root / key

    def load(self, key):
        with self.lock:
            if key in self.live:
                return self.live[key]
            try:
                job = json.loads((self.path(key) / 'job.json').read_text(encoding='utf-8'))
            except (OSError, ValueError):
                raise DubError('Không tìm thấy tác vụ lồng tiếng.', 404) from None
            if job.get('state') in ('running', 'queued'):
                job['state'] = 'paused'
                job['message'] = 'Ứng dụng đã khởi động lại giữa chừng. Bấm Tiếp tục để chạy tiếp (không tạo lại giọng đã có).'
            self.live[key] = job
            return job

    def save(self, job):
        folder = self.path(job['id'])
        tmp = folder / 'job.json.tmp'
        with self.lock:
            tmp.write_text(json.dumps(job, ensure_ascii=False), encoding='utf-8')
            tmp.replace(folder / 'job.json')

    def summary(self, job):
        return {k: job.get(k) for k in ('id', 'name', 'state', 'step', 'steps', 'progress', 'message', 'created', 'outputs', 'warnings', 'duration', 'video_id')} | \
               dict(mode=job.get('options', {}).get('mode', 'lines'), lines=len(job.get('segments') or []), translated=len(job.get('segments') or []) if job.get('paragraph') else sum(1 for s in job.get('segments') or [] if s.get('vi')))

    def jobs(self):
        rows = []
        for folder in self.root.iterdir():
            if folder.is_dir() and re.fullmatch('[a-f0-9]{32}', folder.name) and (folder / 'job.json').is_file():
                try:
                    rows.append(self.summary(self.load(folder.name)))
                except DubError:
                    pass
        return sorted(rows, key=lambda r: r.get('created') or '', reverse=True)

    # -- commands
    def create(self, raw):
        ids = raw.get('video_ids')
        if not isinstance(ids, list) or not 1 <= len(ids) <= 50:
            raise DubError('Chọn từ 1 đến 50 video để lồng tiếng.')
        settings = options(raw.get('options'))
        srts = raw.get('srt') if isinstance(raw.get('srt'), dict) else {}
        made = []
        for vid in ids:
            if not isinstance(vid, str) or not re.fullmatch('[a-f0-9]{32}', vid) or not (self.video_dir / vid / 'source').is_file():
                raise DubError('Video nguồn không còn trong kho. Tải lại video.')
        for vid in ids:
            info = json.loads((self.video_dir / vid / 'source.json').read_text(encoding='utf-8'))
            key = uuid.uuid4().hex
            (self.root / key).mkdir()
            job = dict(id=key, video_id=vid, name=re.sub(r'\.[^.]+$', '', info.get('name', 'video')), duration=info['duration'],
                       created=time.strftime('%Y-%m-%dT%H:%M:%S'), options=settings, state='queued', step='asr',
                       steps={s: 'pending' for s in STEPS}, progress=0, message='Đang chờ lượt.', segments=[], groups=[], warnings=[], outputs={})
            if isinstance(srts.get(vid), str) and srts[vid].strip():
                job['segments'] = parse_srt(srts[vid])
                job['steps']['asr'] = 'skipped'
                job['source_srt'] = True
            self.save(job)
            with self.lock:
                self.live[key] = job
            made.append(key)
            self.enqueue(key, raw)
        return made

    def enqueue(self, key, raw):
        job = self.load(key)
        settings = job['options']
        keys = dict(openai=openai_key(raw), ai33=ai33_key(raw))
        need_openai = any(job['steps'][s] not in ('done', 'skipped') for s in ('asr', 'translate'))
        if need_openai and not keys['openai']:
            raise DubError('Nhập OpenAI API key (dùng cho nhận diện giọng và dịch). Không gửi key trong chat.')
        if not keys['ai33'] and job['steps']['tts'] != 'done':
            raise DubError('Nhập ai33.pro API key (dùng để tạo giọng Việt).')
        if not settings['voice_id'] and job['steps']['tts'] != 'done':
            raise DubError('Chọn giọng đọc (voice_id) trước khi lồng tiếng.')
        with self.lock:
            self.keys[key] = keys
            self.cancels[key] = threading.Event()
            job['state'] = 'queued'
            job['message'] = 'Đang chờ lượt.'
            if key not in self.queue:
                self.queue.append(key)
        self.save(job)
        self.wake.set()

    def proceed(self, key, raw):
        job = self.load(key)
        if job['state'] in ('running', 'queued'):
            raise DubError('Tác vụ đang chạy.')
        if isinstance(raw.get('options'), dict):
            job['options'] = options({**job['options'], **raw['options']})
        start = raw.get('from')
        if start in ('translate', 'tts', 'mix', 'export'):
            for s in STEPS[STEPS.index(start):]:
                if job['steps'][s] != 'skipped':
                    job['steps'][s] = 'pending'
            if start == 'translate':
                job['groups'] = []
                job.pop('paragraph', None)
                for seg in job['segments']:
                    seg.pop('vi', None)
        job['review_passed'] = True
        self.save(job)
        self.enqueue(key, raw)
        return self.load(key)

    def edit_paragraph(self, key, text):
        job = self.load(key)
        if job['state'] in ('running', 'queued'):
            raise DubError('Dừng tác vụ trước khi sửa đoạn văn.')
        if not isinstance(text, str) or not text.strip() or len(text) > 20000:
            raise DubError('Đoạn văn tiếng Việt cần từ 1 đến 20.000 ký tự.')
        text = ' '.join(text.split())
        if text != job.get('paragraph'):
            job['paragraph'] = text
            job['paragraph_syllables'] = syllables(text)
            job['paragraph_edited'] = True
            job['groups'] = []
            for s in ('tts', 'mix', 'export'):
                job['steps'][s] = 'pending'
            job['outputs'] = {}
            if job['state'] == 'done':
                job['state'] = 'review'
                job['message'] = 'Đã sửa đoạn văn. Bấm Tiếp tục để tạo lại file giọng và xuất lại.'
        self.save(job)
        return job

    def edit_lines(self, key, rows):
        job = self.load(key)
        if job['state'] in ('running', 'queued'):
            raise DubError('Dừng tác vụ trước khi sửa câu dịch.')
        if not isinstance(rows, list) or len(rows) > MAX_LINES:
            raise DubError('Danh sách câu không hợp lệ.')
        changed = False
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('i'), int) or not 0 <= row['i'] < len(job['segments']):
                raise DubError('Danh sách câu không hợp lệ.')
            text = row.get('vi', '')
            if not isinstance(text, str) or len(text) > 500:
                raise DubError('Mỗi câu dịch tối đa 500 ký tự.')
            seg = job['segments'][row['i']]
            text = ' '.join(text.split())
            if seg.get('vi', '') != text:
                seg['vi'] = text
                seg['syllables'] = syllables(text)
                seg['edited'] = True
                changed = True
        if changed:
            # Only groups whose text changed need a new TTS task; untouched ones keep their audio.
            old = {g['text']: g for g in job.get('groups') or [] if g.get('file')}
            job['groups'] = [old.get(g['text'], g) | dict(start=g['start'], end=g['end'], lines=g['lines']) for g in group_segments(job['segments'])]
            for s in ('tts', 'mix', 'export'):
                job['steps'][s] = 'pending'
            job['outputs'] = {}
            if job['state'] == 'done':
                job['state'] = 'review'
                job['message'] = 'Đã sửa câu dịch. Bấm Tiếp tục để tạo lại giọng cho các câu đã sửa và xuất lại.'
        self.save(job)
        return job

    def cancel(self, key):
        job = self.load(key)
        with self.lock:
            if key in self.queue:
                self.queue.remove(key)
            event = self.cancels.get(key)
            if event:
                event.set()
            if job['state'] in ('queued', 'running'):
                job['state'] = 'paused'
                job['message'] = 'Đã dừng. Bấm Tiếp tục để chạy tiếp từ bước đang dở.'
        self.save(job)
        return job

    def delete(self, key):
        job = self.load(key)
        if job['state'] in ('running', 'queued'):
            raise DubError('Dừng tác vụ trước khi xóa.')
        with self.lock:
            self.live.pop(key, None)
            shutil.rmtree(self.path(key), ignore_errors=True)

    # -- worker
    def worker(self):
        while True:
            self.wake.wait(2)
            self.wake.clear()
            with self.lock:
                key = self.queue.pop(0) if self.queue else None
            if not key:
                continue
            job = self.load(key)
            cancel = self.cancels.get(key) or threading.Event()
            if cancel.is_set():
                continue
            job['state'] = 'running'
            try:
                self.process(job, self.keys.get(key, {}), cancel)
            except Cancelled:
                job['state'] = 'paused'
                job['message'] = 'Đã dừng. Bấm Tiếp tục để chạy tiếp từ bước đang dở.'
            except (DubError, ai33_audio.AudioError) as exc:
                job['state'] = 'error'
                job['steps'][job['step']] = 'error'
                job['message'] = str(exc)
            except (OSError, ValueError, subprocess.SubprocessError, KeyError, TypeError) as exc:
                job['state'] = 'error'
                job['steps'][job['step']] = 'error'
                job['message'] = 'Lỗi xử lý: ' + str(exc)[:300]
            finally:
                with self.lock:
                    self.keys.pop(key, None)
                self.save(job)

    def progress(self, job, step, fraction, message):
        job['step'] = step
        job['steps'][step] = 'running'
        done = sum(WEIGHTS[s] for s in STEPS if job['steps'][s] in ('done', 'skipped'))
        job['progress'] = min(99, round(done + WEIGHTS[step] * max(0, min(1, fraction))))
        job['message'] = message

    def finish(self, job, step):
        job['steps'][step] = 'done'
        self.save(job)

    def process(self, job, keys, cancel):
        folder = self.path(job['id'])
        source = self.video_dir / job['video_id'] / 'source'
        if not source.is_file():
            raise DubError('Video nguồn đã bị xóa khỏi kho.')
        settings = job['options']
        source = self.trimmed(job, folder, source, cancel)
        info = probe(source)
        job['duration'] = info['duration'] or job['duration']
        def check():
            if cancel.is_set():
                raise Cancelled()

        if job['steps']['asr'] not in ('done', 'skipped'):
            if not info['audio']:
                raise DubError('Video không có âm thanh để nhận diện. Hãy nhập SRT tiếng Trung có sẵn.')
            self.progress(job, 'asr', .1, 'Đang tách âm thanh để nhận diện…')
            run(['ffmpeg', '-hide_banner', '-nostdin', '-y', '-i', str(source), '-vn', '-map', '0:a:0', '-ac', '1', '-ar', '16000',
                 '-c:a', 'libmp3lame', '-b:a', '48k', str(folder / 'asr.mp3')], cancel)
            if (folder / 'asr.mp3').stat().st_size > 25 * 1024 * 1024:
                raise DubError('Âm thanh quá dài cho OpenAI (25 MB). Cắt video ngắn hơn 60 phút.')
            self.progress(job, 'asr', .3, 'Đang nhận diện giọng nói (OpenAI Whisper)…')
            self.save(job)
            result = transcribe_request(folder / 'asr.mp3', keys['openai'], settings['language'])
            rows = [dict(start=round(float(s['start']), 3), end=round(float(s['end']), 3), zh=' '.join(str(s.get('text', '')).split()))
                    for s in result.get('segments') or [] if str(s.get('text', '')).strip() and float(s['end']) > float(s['start'])]
            if not rows:
                raise DubError('Không nhận diện được lời nói trong video.')
            job['segments'] = rows[:MAX_LINES]
            (folder / 'zh.srt').write_text(to_srt(job['segments'], 'zh'), encoding='utf-8')
            (folder / 'asr.mp3').unlink(missing_ok=True)
            self.finish(job, 'asr')
        elif job.get('source_srt') and not (folder / 'zh.srt').is_file():
            (folder / 'zh.srt').write_text(to_srt(job['segments'], 'zh'), encoding='utf-8')
        check()

        if job['steps']['translate'] != 'done' and settings['mode'] == 'paragraph':
            start, seconds = paragraph_window(job)
            limit = max(4, int(seconds * settings['rate']))
            self.progress(job, 'translate', .3, 'Đang dịch thành đoạn văn tiếng Việt…')
            self.save(job)
            text = paragraph_request(keys['openai'], settings['model'], job['segments'], seconds, limit, settings)
            job['paragraph'] = text
            job['paragraph_limit'] = limit
            job['paragraph_syllables'] = syllables(text)
            job['groups'] = []
            job['warnings'] = [w for w in job['warnings'] if not w.startswith(('Đoạn văn', 'Dòng '))]
            if ai_translate.PRICE.search(text) or ai_translate.SPEC.search(text):
                job['warnings'].append('Đoạn văn có thể còn giá hoặc kích thước/thể tích cụ thể; kiểm tra lại trước khi lồng tiếng.')
            if job['paragraph_syllables'] > limit * 1.1:
                job['warnings'].append(f'Đoạn văn dài {job["paragraph_syllables"]}/{limit} tiếng so với thời gian nói; app sẽ đọc nhanh hơn hoặc bạn rút gọn.')
            self.finish(job, 'translate')
            if settings['review'] and not job.get('review_passed'):
                job['state'] = 'review'
                job['step'] = 'tts'
                job['message'] = 'Đã dịch xong đoạn văn. Đọc/sửa lại rồi bấm Tiếp tục để tạo một file giọng ai33.'
                job['progress'] = WEIGHTS['asr'] + WEIGHTS['translate']
                return
        if job['steps']['translate'] != 'done':
            pending = [i for i, s in enumerate(job['segments']) if 'vi' not in s]
            for n in range(0, len(pending), 40):
                batch = pending[n:n + 40]
                self.progress(job, 'translate', n / max(1, len(pending)), f'Đang dịch sang tiếng Việt ({n}/{len(pending)} câu)…')
                self.save(job)
                lines = [dict(id=i, seconds=round(job['segments'][i]['end'] - job['segments'][i]['start'], 2),
                              max_syllables=budget(job['segments'][i], settings['rate']), zh=job['segments'][i]['zh'],
                              before=job['segments'][i - 1]['zh'] if i else '') for i in batch]
                got = translate_request(keys['openai'], settings['model'], lines, settings)
                missing = [i for i in batch if i not in got]
                if missing:
                    got.update(translate_request(keys['openai'], settings['model'], [l for l in lines if l['id'] in missing], settings))
                for i in batch:
                    text = ' '.join(got.get(i, '').split())
                    seg = job['segments'][i]
                    seg['vi'] = text
                    seg['syllables'] = syllables(text)
                    seg['limit'] = budget(seg, settings['rate'])
                check()
            (folder / 'vi.srt').write_text(to_srt(job['segments'], 'vi'), encoding='utf-8')
            job['warnings'] = [w for w in job['warnings'] if not w.startswith('Dòng ')]
            flagged = [i + 1 for i, s in enumerate(job['segments']) if ai_translate.PRICE.search(s.get('vi', '')) or ai_translate.SPEC.search(s.get('vi', ''))]
            if flagged:
                job['warnings'].append(f'Dòng {", ".join(map(str, flagged[:12]))} có thể còn giá hoặc kích thước/thể tích cụ thể; kiểm tra lại ở bảng câu dịch.')
            long = [i + 1 for i, s in enumerate(job['segments']) if s.get('syllables', 0) > s.get('limit', 99) * 1.15]
            if long:
                job['warnings'].append(f'Dòng {", ".join(map(str, long[:12]))}{"…" if len(long) > 12 else ""} dài hơn thời gian nói; app sẽ đọc nhanh hơn hoặc bạn rút gọn ở bảng câu dịch.')
            self.finish(job, 'translate')
            if settings['review'] and not job.get('review_passed'):
                job['state'] = 'review'
                job['step'] = 'tts'
                job['message'] = 'Đã dịch xong. Kiểm tra/sửa câu dịch rồi bấm Tiếp tục để lồng tiếng.'
                job['progress'] = WEIGHTS['asr'] + WEIGHTS['translate']
                return
        check()

        if job['steps']['separate'] != 'done':
            self.separate(job, folder, source, info, cancel)
            self.finish(job, 'separate')
        check()

        if job['steps']['tts'] != 'done':
            self.tts(job, folder, keys, cancel)
            self.finish(job, 'tts')
        check()

        if job['steps']['mix'] != 'done' and settings['mode'] == 'paragraph':
            self.progress(job, 'mix', .2, 'Đang căn giọng theo thời gian video…')
            self.place_paragraph(job, folder, cancel)
            self.finish(job, 'mix')
        if job['steps']['mix'] != 'done':
            self.progress(job, 'mix', .2, 'Đang căn giọng theo thời gian video…')
            job['warnings'] = [w for w in job['warnings'] if not w.startswith('Câu lúc')] + fit(job['groups'], job['duration'], settings['max_tempo'])
            for g in job['groups']:
                if not g.get('file'):
                    continue
                g['raw'] = g['file'].replace('.wav', '.pcm')
                slot = g['clip_seconds'] / g['tempo'] - g['overflow']
                fade = f",afade=t=out:st={max(0, slot - .25):.3f}:d=.25,atrim=duration={slot:.3f}" if g['overflow'] > .05 else ''
                run(['ffmpeg', '-hide_banner', '-nostdin', '-y', '-i', str(folder / g['file']), '-af', tempo_filter(g['tempo']) + fade,
                     '-ac', '1', '-ar', str(VOICE_RATE), '-f', 's16le', str(folder / g['raw'])], cancel)
            mix_voice(job['groups'], folder, job['duration'])
            self.finish(job, 'mix')
        check()

        self.export(job, folder, source, info, cancel)
        self.finish(job, 'export')
        job['state'] = 'done'
        job['progress'] = 100
        job['message'] = 'Đã lồng tiếng xong.' + (f' Đã lưu: {job["outputs"].get("saved_path")}' if job['outputs'].get('saved_path') else '')

    def separate(self, job, folder, source, info, cancel):
        mode = job['options']['background']
        target = folder / 'background.wav'
        target.unlink(missing_ok=True)
        if mode == 'remove' or not info['audio']:
            job['background_used'] = 'none'
            return
        self.progress(job, 'separate', .1, 'Đang xử lý âm thanh gốc…')
        self.save(job)
        base = ['ffmpeg', '-hide_banner', '-nostdin', '-y', '-i', str(source), '-vn', '-map', '0:a:0', '-ac', '2', '-ar', '48000']
        if mode == 'demucs':
            command = demucs_command()
            if not command:
                raise DubError('Chưa cài Demucs. Cài bằng lệnh  pip install demucs  hoặc chọn cách xử lý nền khác.')
            run(base + [str(folder / 'original.wav')], cancel)
            self.progress(job, 'separate', .3, 'Đang tách giọng bằng Demucs (có thể mất vài phút)…')
            self.save(job)
            run(command + ['--two-stems=vocals', '-o', str(folder / 'demucs'), str(folder / 'original.wav')], cancel)
            found = next((folder / 'demucs').rglob('no_vocals.wav'), None)
            if not found:
                raise DubError('Demucs không tạo được nhạc nền.')
            shutil.move(str(found), target)
            shutil.rmtree(folder / 'demucs', ignore_errors=True)
            (folder / 'original.wav').unlink(missing_ok=True)
        elif mode == 'center':
            # Voices are usually mixed in the centre: L−R removes them; low frequencies are added back from the original.
            if (info['audio'].get('channels') or 1) < 2:
                job['warnings'].append('Âm thanh gốc là mono nên không lọc giọng giữa được; đã chuyển sang giảm âm khi có lời.')
                job['options']['background'] = 'duck'
                return self.separate(job, folder, source, info, cancel)
            (folder / 'center.ffgraph').write_text('[0:a:0]aformat=channel_layouts=stereo,asplit=2[a][b];[a]pan=stereo|c0=c0-c1|c1=c1-c0[side];'
                                                   '[b]lowpass=f=150,volume=0.8[bass];[side][bass]amix=inputs=2:normalize=0[out]', encoding='utf-8')
            run(['ffmpeg', '-hide_banner', '-nostdin', '-y', '-i', str(source), '-filter_complex_script', str(folder / 'center.ffgraph'),
                 '-map', '[out]', '-ar', '48000', str(target)], cancel)
        elif mode == 'duck':
            level = job['options']['duck_level'] / 100
            spans = '+'.join(f'between(t,{max(0, s["start"] - .15):.2f},{s["end"] + .15:.2f})' for s in job['segments']) or '0'
            (folder / 'duck.ffgraph').write_text(f"[0:a:0]aformat=channel_layouts=stereo,volume={level}:enable='{spans}'[out]", encoding='utf-8')
            run(['ffmpeg', '-hide_banner', '-nostdin', '-y', '-i', str(source), '-filter_complex_script', str(folder / 'duck.ffgraph'),
                 '-map', '[out]', '-ar', '48000', str(target)], cancel)
        else:
            run(base + [str(target)], cancel)
        job['background_used'] = job['options']['background']

    def tts(self, job, folder, keys, cancel):
        settings = job['options']
        paragraph = settings['mode'] == 'paragraph'
        if not job.get('groups'):
            if paragraph:
                if not job.get('paragraph'):
                    raise DubError('Chưa có đoạn văn tiếng Việt để tạo giọng.')
                job['groups'] = [dict(start=paragraph_window(job)[0], end=job['duration'], text=job['paragraph'], lines=list(range(len(job['segments']))))]
            else:
                job['groups'] = group_segments(job['segments'])
        groups = job['groups']
        todo = [g for g in groups if not g.get('file')]
        if not todo:
            return
        base = dict(api_key=keys['ai33'], voice_id=settings['voice_id'], speed=settings['voice_speed'])
        if settings['dictionary_id']:
            base['pronunciation_dictionary_id'] = settings['dictionary_id']
        # MP3 only: no transcript/SRT is requested from ai33 (subtitles are timed locally from the voice's pauses)
        flight = []
        waited = time.monotonic()
        while todo or flight:
            if cancel.is_set():
                raise Cancelled()
            # Submit up to 4 tasks at once; each task id is saved before polling so nothing is bought twice.
            while todo and len(flight) < 4:
                g = todo[0]
                if not g.get('task_id'):
                    try:
                        g['task_id'] = ai33_audio.create_tts(dict(base, text=g['text'], file_name=f'{job["name"][:60]}-{groups.index(g) + 1}'))['task_id']
                    except ai33_audio.AudioError as exc:
                        if exc.status == 429:
                            break
                        raise
                    self.save(job)
                flight.append(todo.pop(0))
            time.sleep(3)
            for g in list(flight):
                detail = self.poll(g, keys, job)
                if detail is None:
                    continue
                if detail['status'] == 'error':
                    raise DubError(f'ai33.pro báo lỗi khi tạo giọng câu "{g["text"][:40]}…". Kiểm tra credit/giọng rồi bấm Tiếp tục.')
                if detail['status'] == 'done' and detail['audio_url']:
                    download = folder / f'g{groups.index(g)}.download'
                    audio_files.download(detail['audio_url'], download)
                    g['file'] = f'g{groups.index(g)}.wav'
                    run(['ffmpeg', '-hide_banner', '-nostdin', '-y', '-i', str(download), '-ac', '1', '-ar', str(VOICE_RATE), str(folder / g['file'])], cancel)
                    download.unlink(missing_ok=True)
                    with wave.open(str(folder / g['file'])) as w:
                        g['clip_seconds'] = round(w.getnframes() / w.getframerate(), 3)
                    flight.remove(g)
                    waited = time.monotonic()
                    self.save(job)
            ready = sum(1 for g in groups if g.get('file'))
            self.progress(job, 'tts', ready / len(groups), 'Đang tạo một file giọng Việt ai33…' if paragraph else f'Đang tạo giọng Việt ai33 ({ready}/{len(groups)} câu)…')
            retrying = next((g for g in flight if g.get('poll_errors')), None)
            if retrying:
                job['message'] = retrying['poll_message']
            if time.monotonic() - waited > 900:
                raise DubError('ai33.pro chưa trả giọng sau 15 phút. Bấm Tiếp tục để kiểm tra lại (không tạo trùng).')

    def poll(self, g, keys, job):
        """Task status; a failing /v1/task call falls back to the task history, transient errors are retried
        (only bad key / credit / permission stop the job)."""
        raw = dict(api_key=keys['ai33'], task_id=g['task_id'])
        try:
            detail = ai33_audio.get_task(raw)
            g.pop('poll_errors', None)
            return detail
        except ai33_audio.AudioError as exc:
            if exc.status in (400, 401, 402, 403):
                raise
            error = str(exc)
        try:
            found = ai33_audio.find_task(raw, g['task_id'])
            if found:
                g.pop('poll_errors', None)
                return found
        except ai33_audio.AudioError as exc:
            error = str(exc)
        g['poll_errors'] = g.get('poll_errors', 0) + 1
        g['poll_message'] = f'ai33 chưa trả kết quả, đang thử lại (lần {g["poll_errors"]})… {error}'
        if g['poll_errors'] >= 200:  # ~10 minutes of failures in a row
            raise DubError(error + ' Nếu ai33 đã tạo xong MP3, bấm "⬆ Dùng MP3 đã tạo" để tải file lên và xuất tiếp.')
        return None

    def use_voice(self, key, upload):
        """Use an MP3 the user downloaded from ai33 (or any voice file) as the single paragraph voice."""
        job = self.load(key)
        if job['state'] in ('running', 'queued'):
            raise DubError('Dừng tác vụ trước khi thay file giọng.')
        if job['options']['mode'] != 'paragraph':
            raise DubError('Tải file giọng chỉ dùng cho chế độ "Đoạn văn liền · 1 file giọng".')
        if not job['segments']:
            raise DubError('Tác vụ chưa có lời thoại để căn giọng.')
        folder = self.path(key)
        try:
            run(['ffmpeg', '-hide_banner', '-nostdin', '-y', '-i', str(upload), '-map', '0:a:0', '-vn', '-ac', '1', '-ar', str(VOICE_RATE), str(folder / 'g0.wav')])
        except DubError:
            raise DubError('Không đọc được file âm thanh. Dùng MP3/WAV/M4A hợp lệ.') from None
        with wave.open(str(folder / 'g0.wav')) as w:
            seconds = round(w.getnframes() / w.getframerate(), 3)
        if seconds < .3:
            raise DubError('File giọng quá ngắn.')
        old = (job.get('groups') or [{}])[0]
        job['groups'] = [dict(start=paragraph_window(job)[0], end=job['duration'], text=job.get('paragraph') or old.get('text', ''),
                              lines=list(range(len(job['segments']))), task_id=old.get('task_id', ''), file='g0.wav', clip_seconds=seconds, uploaded=True)]
        if not job.get('paragraph'):
            job['paragraph'] = ''
        for s in ('asr', 'translate'):
            if job['steps'][s] not in ('done', 'skipped'):
                job['steps'][s] = 'skipped'
        job['steps']['tts'] = 'done'
        for s in ('mix', 'export'):
            job['steps'][s] = 'pending'
        job['outputs'] = {}
        job['review_passed'] = True
        job['state'] = 'paused'
        job['message'] = f'Đã nhận file giọng ({seconds:.1f}s). Đang xuất video…'
        self.save(job)
        self.enqueue(key, {})
        return self.load(key)

    def trimmed(self, job, folder, source, cancel):
        """Cut trim_start seconds off the beginning and trim_end off the end (frame-accurate re-encode) before anything
        else, so recognition, voice and subtitles all use the trimmed timeline. Changing the cut restarts the job."""
        settings = job['options']
        a, b = settings.get('trim_start', 0), settings.get('trim_end', 0)
        target = folder / 'trimmed.mp4'
        sign = f'{a:.3f}:{b:.3f}'
        if job.get('trim_sign', '0.000:0.000') != sign:
            if any(job['steps'][s] == 'done' for s in STEPS):
                for s in STEPS:
                    if job['steps'][s] != 'skipped':
                        job['steps'][s] = 'pending'
                job['groups'] = []
                job.pop('paragraph', None)
                for seg in job['segments']:
                    seg.pop('vi', None)
                if not job.get('source_srt'):
                    job['segments'] = []
            target.unlink(missing_ok=True)
            job['trim_sign'] = sign
        if not a and not b:
            return source
        if not target.is_file():
            total = probe(source)['duration']
            keep = total - a - b
            if keep < 1:
                raise DubError(f'Cắt đầu {a}s và cuối {b}s thì video còn quá ngắn ({max(0, keep):.1f}s).')
            self.progress(job, job['step'] if job['step'] in STEPS else 'asr', 0, f'Đang cắt video: bỏ {a}s đầu, {b}s cuối…')
            self.save(job)
            run(['ffmpeg', '-hide_banner', '-nostdin', '-y', '-ss', f'{a:.3f}', '-i', str(source), '-t', f'{keep:.3f}', '-map', '0:v:0', '-map', '0:a?',
                 *self.encoder_args('cpu', 'high'), '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', str(target)], cancel)
        return target

    def place_paragraph(self, job, folder, cancel):
        """Put the single voice file at the first spoken line and make it end with the video.
        align: 'auto' = read faster only when too long · 'voice' = MP3 follows the video (faster or slower)
        · 'video' = video follows the MP3 (sped up or slowed down, the first spoken moment moves with it)."""
        settings = job['options']
        g = job['groups'][0]
        start = g['start']
        room = max(.5, job['duration'] - start - .05)
        tempo, stretch, overflow = 1.0, 1.0, 0.0
        need = g['clip_seconds'] / room
        if settings['align'] == 'video':
            # video follows the MP3: faster or slower so the voice ends just before the video does
            stretch = max(.25, min(4.0, (g['clip_seconds'] + .3) / max(.5, job['duration'] - start)))
            if abs(stretch - 1) < .01:
                stretch = 1.0
        elif settings['align'] == 'voice' or need > 1:
            # MP3 follows the video (both ways, kept in a natural range) — or, in 'auto', only when it is too long
            tempo = min(max(need, .8 if settings['align'] == 'voice' else 1.0), settings['max_tempo'])
        if stretch == 1:
            overflow = max(0.0, g['clip_seconds'] / tempo - room)
        job['video_stretch'] = round(stretch, 4)
        job['output_duration'] = round(job['duration'] * stretch, 3)
        place = round(start * stretch, 3)
        g.update(tempo=round(tempo, 4), overflow=round(overflow, 2), raw=g['file'].replace('.wav', '.pcm'), place=place)
        job['warnings'] = [w for w in job['warnings'] if not w.startswith(('Giọng dài', 'Video được'))]
        if overflow > .05:
            job['warnings'].append(f'Giọng dài hơn video {overflow:.1f}s dù đã đọc nhanh {tempo:.2f}×; phần cuối được làm nhỏ dần. Rút gọn đoạn văn hoặc chọn "Video khớp MP3".')
        if stretch != 1:
            job['warnings'].append(f'Video được {"làm chậm" if stretch > 1 else "tua nhanh"} cho khớp giọng đọc: dài {job["output_duration"]:.1f}s (gốc {job["duration"]:.1f}s).')
        length = g['clip_seconds'] / tempo - overflow
        fade = f",afade=t=out:st={max(0, length - .3):.3f}:d=.3,atrim=duration={length:.3f}" if overflow > .05 else ''
        run(['ffmpeg', '-hide_banner', '-nostdin', '-y', '-i', str(folder / g['file']), '-af', tempo_filter(tempo) + fade,
             '-ac', '1', '-ar', str(VOICE_RATE), '-f', 's16le', str(folder / g['raw'])], cancel)
        mix_voice(job['groups'], folder, job['output_duration'])
        # subtitles follow the voice: sentences are spread by length, then each change snaps to the nearest pause in the audio
        pauses = [t / tempo for t in silences(folder / g['file'])]
        job['vi_lines'] = [l for l in sentence_lines(job.get('paragraph') or '', place, length, pauses) if l['start'] < job['output_duration']]

    def export(self, job, folder, source, info, cancel):
        settings = job['options']
        self.progress(job, 'export', .1, 'Đang xuất video MP4…')
        self.save(job)
        stretch = job.get('video_stretch', 1) if settings['mode'] == 'paragraph' else 1
        duration = job.get('output_duration', job['duration']) if settings['mode'] == 'paragraph' else job['duration']
        subtitle_rows = job.get('vi_lines') if settings['mode'] == 'paragraph' else job['segments']
        background = folder / 'background.wav'
        has_bg = background.is_file()
        subs = settings['subtitles']
        (folder / 'vi.srt').write_text(to_srt(subtitle_rows or [], 'vi'), encoding='utf-8')
        args = ['ffmpeg', '-hide_banner', '-nostdin', '-y', '-i', str(source), '-i', 'voice.wav']
        if has_bg:
            args += ['-i', 'background.wav']
        if subs == 'soft':
            args += ['-i', 'vi.srt']
        graph = [f'[1:a]aresample=48000,aformat=channel_layouts=stereo,volume={settings["voice_volume"] / 100}[voice]']
        if has_bg:
            graph.append(f'[2:a]aresample=48000,' + (tempo_filter(1 / stretch) + ',' if stretch != 1 else '') + f'volume={settings["background_volume"] / 100},apad[bg]')
            graph.append('[bg][voice]amix=inputs=2:duration=longest:normalize=0[mixed]')
        else:
            graph.append('[voice]anull[mixed]')
        finish = ('loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000,' if settings['loudness'] == 'tiktok' else '') + 'alimiter=limit=0.95:level=false'
        graph.append(f'[mixed]{finish},atrim=duration={duration}[aout]')
        video = info['video']
        identity = frame_identity(settings)
        chosen = self.pick_overlays(job, duration)
        copy = stretch == 1 and identity and not chosen and video.get('codec_name') == 'h264' and video.get('pix_fmt') in ('yuv420p', 'yuvj420p')
        filters = not copy
        if filters:
            width, height = frame_size(settings, video)
            # frame → random overlays
            lines, _ = frame_graph(settings, video, [f'setpts=PTS*{stretch:.6f}'] if stretch != 1 else [], [])
            lines[-1] = lines[-1][:-len('[vout]')] + '[framed]'
            graph.extend(lines)
            base, index = 'framed', 2 + has_bg + (subs == 'soft')
            for k, item in enumerate(chosen):
                if settings['overlay_timing'] == 'sequence' and item.get('sequence'):
                    # joined clips: each normalised to the frame, concatenated, then cut to the video's length
                    parts = []
                    for n, clip in enumerate(item['sequence']):
                        meta = self.overlay(clip)
                        if not meta:
                            continue
                        args += (['-loop', '1', '-t', '3'] if meta['still'] else []) + ['-i', str(self.overlay_dir / meta['file'])]
                        graph.append(f'[{index}:v]{overlay_fit(width, height)},format=rgba[sq{k}_{n}]')
                        parts.append(f'[sq{k}_{n}]')
                        index += 1
                    graph.append(''.join(parts) + f'concat=n={len(parts)}:v=1:a=0[seq{k}]')
                    source = f'[seq{k}]'
                else:
                    meta = self.overlay(item['id'])
                    path = str(self.overlay_dir / meta['file'])
                    if meta['still']:
                        args += ['-loop', '1', '-t', str(duration if settings['overlay_timing'] == 'loop' else min(duration, 4)), '-i', path]
                    else:
                        args += (['-stream_loop', '-1'] if settings['overlay_timing'] == 'loop' else []) + ['-i', path]
                    source = f'[{index}:v]'
                    index += 1
                more, base = overlay_chain(source, dict(item, k=k), width, height, settings, base, duration)
                graph.extend(more)
            graph.append(f'[{base}]format=yuv420p[vout]')
        (folder / 'export.ffgraph').write_text(';\n'.join(graph), encoding='utf-8')
        args += ['-filter_complex_script', 'export.ffgraph', '-map', '[vout]' if filters else '0:v:0', '-map', '[aout]']
        if subs == 'soft':
            args += ['-map', str(3 if has_bg else 2) + ':s:0', '-c:s', 'mov_text', '-metadata:s:s:0', 'language=vie']
        args += (['-c:v', 'copy'] if copy else self.encoder_args(settings['encoder'], 'high')) + ['-c:a', 'aac', '-b:a', '192k',
                 '-t', str(duration), '-movflags', '+faststart', 'dubbed.mp4']
        try:
            run(args, cancel, cwd=folder)
        except DubError:
            if settings['encoder'] == 'cpu' or copy:
                raise
            args = [a for a in args]
            i = args.index('-c:a')
            start = max(j for j in range(i) if args[j] == '-c:v')
            run(args[:start] + self.encoder_args('cpu', 'high') + args[i:], cancel, cwd=folder)
        job['outputs'] = dict(video=f'/dub/{job["id"]}/download', srt=f'/dub/{job["id"]}/srt/vi', srt_zh=f'/dub/{job["id"]}/srt/zh')
        try:
            if output_folder.load(self.settings_path)['auto_save']:
                saved = output_folder.deliver(self.settings_path, folder / 'dubbed.mp4', job['name'] + '-long-tieng')
                job['outputs']['saved_path'] = str(saved)
                if subs in ('file', 'soft'):
                    shutil.copyfile(folder / 'vi.srt', saved.with_suffix('.srt'))
        except (ValueError, OSError) as exc:
            job['warnings'].append(str(exc))

    # ---- overlay library (videos/GIF/PNG put on top of dubbed videos, picked at random per video)
    def overlays(self):
        rows = []
        for meta in self.overlay_dir.glob('*.json'):
            try:
                item = json.loads(meta.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            if isinstance(item, dict) and item.get('id') == meta.stem and (self.overlay_dir / item.get('file', '')).is_file():
                rows.append(item)
        return sorted(rows, key=lambda r: r.get('created', ''), reverse=True)

    def overlay(self, key):
        if not isinstance(key, str) or not re.fullmatch('[a-f0-9]{32}', key):
            return None
        return next((o for o in self.overlays() if o['id'] == key), None)

    def import_overlay(self, upload, name):
        ext = Path(str(name)).suffix.lower()
        if ext not in OVERLAY_TYPES:
            raise DubError('Overlay cần là video (MP4, MOV, WebM), GIF hoặc ảnh PNG/JPG.')
        key = uuid.uuid4().hex
        target = self.overlay_dir / (key + ext)
        shutil.move(str(upload), target)
        info = probe(target)
        if not info['video']:
            target.unlink(missing_ok=True)
            raise DubError('Không đọc được hình ảnh trong file overlay.')
        still = ext in ('.png', '.jpg', '.jpeg', '.webp') or info['duration'] < .1
        try:
            run(['ffmpeg', '-hide_banner', '-nostdin', '-y', '-ss', str(min(1, info['duration'] / 3)) if not still else '0', '-i', str(target),
                 '-frames:v', '1', '-vf', 'scale=160:-2', str(self.overlay_dir / (key + '.jpg'))], timeout=30)
        except DubError:
            pass
        item = dict(id=key, name=re.sub(r'[\x00-\x1f<>:"/\\|?*]', '_', Path(str(name)).name)[:120], file=target.name, still=still,
                    duration=0 if still else round(info['duration'], 2), width=int(info['video'].get('width') or 0), height=int(info['video'].get('height') or 0),
                    created=time.strftime('%Y-%m-%dT%H:%M:%S'))
        (self.overlay_dir / (key + '.json')).write_text(json.dumps(item, ensure_ascii=False), encoding='utf-8')
        return item

    def delete_overlay(self, key):
        item = self.overlay(key)
        if not item:
            raise DubError('Không tìm thấy overlay.', 404)
        for path in (self.overlay_dir / item['file'], self.overlay_dir / (key + '.json'), self.overlay_dir / (key + '.jpg')):
            path.unlink(missing_ok=True)

    def pick_overlays(self, job, duration):
        """Random overlays for this video (kept in the job so re-exports look the same)."""
        settings = job['options']
        if not settings['overlay']:
            return []
        sign = json.dumps([settings[k] for k in ('overlay_ids', 'overlay_count', 'overlay_timing')])
        chosen = [o for o in job.get('overlays') or [] if self.overlay(o['id'])]
        if job.get('overlay_sign') == sign and chosen:
            return chosen
        library = self.overlays()
        pool = [o for o in library if not settings['overlay_ids'] or o['id'] in settings['overlay_ids']]
        job['warnings'] = [w for w in job.get('warnings') or [] if not w.startswith('Overlay')]
        if not pool:
            # overlay is optional: an empty library never blocks the video, it is just exported without one
            job['warnings'].append('Overlay đang bật nhưng thư viện overlay trống nên video được xuất không có overlay.')
            job['overlays'], job['overlay_sign'] = [], None
            return []
        picked = random.sample(pool, min(settings['overlay_count'], len(pool)))
        job['overlays'] = [dict(id=o['id'], name=o['name'], start=round(random.uniform(0, max(0, duration - (o['duration'] or 4))), 2)
                                if settings['overlay_timing'] == 'random' else 0) for o in picked]
        if settings['overlay_timing'] == 'sequence':
            # each layer: random clips joined one after another until the video is covered (no clip twice in a row)
            for layer in job['overlays']:
                seq, total, last = [layer['id']], self.clip_length(layer['id']), layer['id']
                while total < duration and len(seq) < 60:
                    options = [o for o in pool if o['id'] != last] or pool
                    nxt = random.choice(options)
                    seq.append(nxt['id'])
                    total += self.clip_length(nxt['id'])
                    last = nxt['id']
                layer['sequence'] = seq
                layer['name'] = ' + '.join(self.overlay(i)['name'] for i in seq[:3]) + (f' … ({len(seq)} đoạn)' if len(seq) > 3 else '')
        job['overlay_sign'] = sign
        return job['overlays']

    def clip_length(self, key):
        item = self.overlay(key)
        return 3.0 if not item or item['still'] else max(.2, item['duration'])

    def to_editor(self, key, new_video, import_audio):
        """Hand the result to the editor: video with background only + the Vietnamese voice as an MP3 asset."""
        job = self.load(key)
        folder = self.path(key)
        if job['state'] != 'done' or not (folder / 'voice.wav').is_file():
            raise DubError('Lồng tiếng chưa xong.')
        source = folder / 'trimmed.mp4' if (folder / 'trimmed.mp4').is_file() else self.video_dir / job['video_id'] / 'source'
        target = new_video()
        background = folder / 'background.wav'
        args = ['ffmpeg', '-hide_banner', '-nostdin', '-y', '-i', str(source)] + (['-i', str(background)] if background.is_file() else []) + \
               ['-map', '0:v:0'] + (['-map', '1:a:0', '-c:a', 'aac', '-b:a', '192k'] if background.is_file() else []) + \
               (['-c:v', 'copy'] if job.get('video_stretch', 1) == 1 or job['options']['mode'] != 'paragraph' else
                ['-filter:v', f'setpts=PTS*{job["video_stretch"]:.6f}', *self.encoder_args('cpu', 'high')] +
                (['-filter:a', tempo_filter(1 / job['video_stretch'])] if background.is_file() else [])) + \
               ['-t', str(job.get('output_duration', job['duration'])), '-f', 'mp4', str(target)]
        run(args)
        asset = import_audio(folder / 'voice.wav', job['name'] + ' · giọng Việt')
        return dict(audio_asset_id=asset['asset_id'])
