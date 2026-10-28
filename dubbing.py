"""Automatic Chinese → Vietnamese dubbing.

01 Nhận diện  OpenAI Whisper (whisper-1) → Chinese SRT with timestamps (or an SRT the user already has)
02 Dịch       OpenAI → natural Vietnamese, each line sized to the time it has on screen
03 Tách âm    background kept by: Demucs (if installed), centre-channel cancel, ducking under speech, or removed
04 Lồng tiếng ai33.pro TTS per sentence group → fitted (gentle speed-up) and placed at the original timestamps
05 Xuất       MP4 H.264 + AAC, Vietnamese voice, optional Vietnamese SRT (separate file or soft track; never burned into the picture)

Jobs run in worker threads (1 to MAX_PARALLEL at a time, set on the queue). Their state (segments, translations, ai33 task ids) is saved in
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
import sys
import threading
import time
import unicodedata
import uuid
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib import request, error
import ai33_audio
import ai_translate
import audio_files
import output_folder
import secrets_store
from media_engine import tempo as tempo_filter, design_layers
import design as design_mod
from fonts import FONTS

OPENAI = os.environ.get('REVIEW_OPENAI_BASE', 'https://api.openai.com/v1/').rstrip('/') + '/'
STEPS = ('asr', 'translate', 'separate', 'tts', 'mix', 'export')
WEIGHTS = dict(asr=15, translate=10, separate=15, tts=40, mix=10, export=10)
MAX_PARALLEL = 4
# Output frame for the dubbed video; 'source' keeps the original size (even-rounded).
CANVAS = {'source': None, '9:16': (1080, 1920), '1:1': (1080, 1080), '4:5': (1080, 1350), '16:9': (1920, 1080)}
BACKGROUND = ('duck', 'center', 'demucs', 'remove', 'keep')
SUBTITLES = ('none', 'file', 'soft')
VOICE_RATE = 24000
MAX_LINES = 600
DEFAULTS = dict(language='zh', model=ai_translate.DEFAULT_MODEL, rate=4.2, pronoun='neutral', notes='', no_price=True,
                voice_id='', voice_speed=1.0, dictionary_id=None, max_tempo=1.1, min_tempo=0.98, video_speed_min=0.85, video_speed_max=1.2, background='duck', duck_level=12,
                background_volume=100, voice_volume=100, subtitles='file', loudness='tiktok', review=False, encoder='cpu', instructions='', mode='paragraph', align='auto', style='review',
                frame_canvas='source', frame_fit='cover', frame_zoom=100, frame_x=0, frame_y=0, frame_rotate=0, frame_flip='none', trim_start=0, trim_end=0,
                overlay=False, overlay_ids=[], overlay_count=1, overlay_blend='screen', overlay_opacity=60, overlay_timing='loop', end_with_voice=True,
                image=False, image_id='', image_x=0, image_y=0, image_w=60, image_h=0, image_rotate=0, image_flip='none', image_blend='normal',
                image_opacity=100, image_layer='below',
                design=None, title_source='ai', body_source='ai', title_chars=30, body_min_chars=50, body_max_chars=100, review_texts=False, design_bg=True, design_title=True, design_body=True,
                adjust=False, adjust_brightness=0, adjust_contrast=0, adjust_saturation=0, adjust_sharpen=0)
TEXT_SOURCES = ('ai', 'fixed', 'file', 'none')
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
    for key, lo, hi in (('frame_zoom', 25, 400), ('frame_x', -400, 400), ('frame_y', -400, 400), ('frame_rotate', -180, 180), ('overlay_opacity', 0, 100), ('trim_start', 0, 120), ('trim_end', 0, 120), ('rate', 2.5, 7), ('voice_speed', .5, 1.5), ('max_tempo', 1, 1.6), ('min_tempo', .5, 1), ('video_speed_min', .25, 1), ('video_speed_max', 1, 4), ('duck_level', 0, 100),
                        ('background_volume', 0, 200), ('voice_volume', 0, 300),
                        ('image_x', -150, 150), ('image_y', -150, 150), ('image_w', 1, 400), ('image_h', 0, 400), ('image_rotate', -180, 180), ('image_opacity', 0, 100),
                        ('adjust_brightness', -100, 100), ('adjust_contrast', -100, 100), ('adjust_saturation', -100, 100), ('adjust_sharpen', 0, 100)):
        num(key, lo, hi)
    if raw.get('subtitles') == 'burn':  # burned-in subtitles were removed; old saved settings get the .srt file instead
        raw = dict(raw, subtitles='file')
    for key, allowed in (('language', ('zh', 'en', 'auto')), ('background', BACKGROUND), ('subtitles', SUBTITLES),
                         ('loudness', ('off', 'tiktok')), ('pronoun', tuple(PRONOUNS)), ('mode', ('paragraph', 'lines', 'ai33', 'design')), ('align', ('auto', 'voice', 'video')), ('style', tuple(ai_translate.STYLES)), ('frame_canvas', tuple(CANVAS)), ('frame_fit', ('cover', 'contain', 'blur')),
                         ('frame_flip', ('none', 'h', 'v', 'hv')), ('overlay_blend', ('normal', 'screen', 'key')), ('overlay_timing', ('loop', 'sequence', 'random')),
                         ('image_flip', ('none', 'h', 'v', 'hv')), ('image_blend', tuple(IMAGE_BLENDS)), ('image_layer', ('below', 'above')),
                         ('title_source', TEXT_SOURCES), ('body_source', TEXT_SOURCES)):
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
    for key, lo, hi in (('title_chars', 5, 160), ('body_min_chars', 0, 600), ('body_max_chars', 10, 600)):
        v = raw.get(key, DEFAULTS[key])
        if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
            raise DubError('Thông số không hợp lệ: ' + key)
        out[key] = v
    if out['body_min_chars'] > out['body_max_chars']:
        raise DubError('Số ký tự nội dung: tối thiểu phải nhỏ hơn tối đa.')
    # nền + khung + tiêu đề + nội dung: the editor's design settings (720×1280 design pixels), validated the same way
    if raw.get('design') not in (None, {}):
        if not isinstance(raw['design'], dict) or len(json.dumps(raw['design'])) > 60000:
            raise DubError('Thiết kế không hợp lệ.')
        try:
            out['design'] = design_mod.settings(dict(raw['design']))
        except ValueError as exc:
            raise DubError('Thiết kế: ' + str(exc)) from None
        out['frame_canvas'] = '9:16'
    image_id = raw.get('image_id', '')
    if not isinstance(image_id, str) or (image_id and not re.fullmatch('[a-f0-9]{32}', image_id)):
        raise DubError('Ảnh overlay không hợp lệ.')
    out['image_id'] = image_id
    for key in ('no_price', 'review', 'overlay', 'end_with_voice', 'image', 'review_texts', 'design_bg', 'design_title', 'design_body', 'adjust'):
        v = raw.get(key, DEFAULTS[key])
        if not isinstance(v, bool):
            raise DubError('Thông số không hợp lệ: ' + key)
        out[key] = v
    # the three groups of the tab, each with its switch: background + frame, title, body (all off = plain video)
    if raw.get('design_text') is False:   # one "chữ" switch before 0.22
        out['design_title'] = out['design_body'] = False
    if out.get('design') and not out['design_bg']:
        out['design'] = dict(out['design'], background='none', frame_style='none')
    if out.get('design') and not out['design_title']:
        out['title_source'] = 'none'
    if out.get('design') and not out['design_body']:
        out['body_source'] = 'none'
    if not (out['design_bg'] or out['design_title'] or out['design_body']):
        out['design'] = None
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


def parallel_count(value):
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= MAX_PARALLEL:
        raise DubError(f'Số video chạy cùng lúc phải từ 1 đến {MAX_PARALLEL}.')
    return value


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


DEMUCS_RUNNER = Path(__file__).resolve().parent / 'demucs_runner.py'
DEMUCS_ENV = Path(__file__).resolve().parent / '.local' / 'demucs-env'   # the app's own Python environment for Demucs
DEMUCS_PACKAGES = ['demucs', 'soundfile']
_demucs = {}
INSTALL = dict(state='idle', log='', error='')
_install_lock = threading.Lock()


def env_python(env):
    return env / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def demucs_command(refresh=False):
    """Demucs (optional) gives real AI vocal separation; otherwise FFmpeg modes are used.

    Looks in the app's own environment first, then the Python running the app and the other Pythons on PATH (pip
    often installs the `demucs` command outside PATH on Windows). Demucs runs through demucs_runner.py, which saves
    the result without torchaudio's new torchcodec dependency. Falls back to a plain `demucs` command."""
    if refresh or 'cmd' not in _demucs:
        candidates = [[str(env_python(DEMUCS_ENV))]] if env_python(DEMUCS_ENV).is_file() else []
        candidates.append([sys.executable])
        for name in ('python', 'python3'):
            found = shutil.which(name)
            if found:
                candidates.append([found])
        if os.name == 'nt' and shutil.which('py'):
            candidates.append([shutil.which('py'), '-3'])
        cmd = None
        for python in candidates:
            try:
                check = subprocess.run(python + ['-c', "import importlib.util,sys;sys.exit(importlib.util.find_spec('demucs') is None)"],
                                       capture_output=True, timeout=30)
            except (OSError, subprocess.SubprocessError):
                continue
            if check.returncode == 0:
                cmd = python + [str(DEMUCS_RUNNER)]
                break
        if not cmd and shutil.which('demucs'):
            cmd = [shutil.which('demucs')]
        _demucs['cmd'] = cmd
    return _demucs['cmd']


def demucs_status(refresh=False):
    return dict(INSTALL, available=bool(demucs_command(refresh)))


def install_demucs():
    """pip install Demucs in the background, into .local/demucs-env (no admin rights, nothing changes in the system
    Python). If that environment cannot be created, installs for the current user instead."""
    with _install_lock:
        if INSTALL['state'] == 'running':
            return demucs_status()
        INSTALL.update(state='running', log='Đang chuẩn bị…', error='')
    def work():
        lines = []
        def step(cmd):
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
            for line in proc.stdout:
                if line.strip():
                    lines.append(line.rstrip()[:300])
                    INSTALL['log'] = '\n'.join(lines[-8:])
            return proc.wait()
        try:
            python = env_python(DEMUCS_ENV)
            if not python.is_file():
                lines.append('Tạo môi trường riêng cho Demucs…')
                if step([sys.executable, '-m', 'venv', str(DEMUCS_ENV)]) or not python.is_file():
                    shutil.rmtree(DEMUCS_ENV, ignore_errors=True)
            if python.is_file():
                step([str(python), '-m', 'pip', 'install', '--upgrade', 'pip'])
                code = step([str(python), '-m', 'pip', 'install', '--upgrade', *DEMUCS_PACKAGES])
            else:
                code = step([sys.executable, '-m', 'pip', 'install', '--user', '--upgrade', *DEMUCS_PACKAGES])
            ok = code == 0 and demucs_command(True)
            INSTALL.update(state='done' if ok else 'error',
                           error='' if ok else 'Cài Demucs chưa thành công. Xem vài dòng cuối bên dưới (thường do mạng hoặc phiên bản Python quá mới/cũ).')
        except Exception as exc:  # noqa: BLE001 — shown to the user, never fatal for the app
            INSTALL.update(state='error', error='Không chạy được pip: ' + str(exc)[:200])
    threading.Thread(target=work, daemon=True).start()
    return demucs_status()


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


SOURCE_NAMES = {'zh': 'tiếng Trung', 'en': 'tiếng Anh', 'auto': 'tiếng nước ngoài (tiếng Trung, tiếng Anh…)'}

# Translation models shown in the app: USD per 1M tokens (input, output) from OpenAI's public price list, for an
# estimate only — the real bill follows OpenAI's current prices. `think` = reasoning model (extra hidden output tokens).
MODELS = [
    dict(id='gpt-4.1-nano', price=(0.10, 0.40), think=False, use='Rẻ nhất · video ngắn, lời đơn giản; văn phong kém tự nhiên hơn'),
    dict(id='gpt-4o-mini', price=(0.15, 0.60), think=False, use='Rất rẻ · dịch nhanh, ổn định cho số lượng lớn'),
    dict(id='gpt-4.1-mini', price=(0.40, 1.60), think=False, use='Khuyên dùng · cân bằng giá và chất lượng, giữ quy tắc tốt'),
    dict(id='gpt-5-mini', price=(0.25, 2.00), think=True, use='Có suy luận · hiểu ý tốt hơn, chậm hơn một chút'),
    dict(id='gpt-4.1', price=(2.00, 8.00), think=False, use='Văn phong hay · review bán hàng, cần lời mượt'),
    dict(id='gpt-4o', price=(2.50, 10.00), think=False, use='Chất lượng cao · đắt hơn gpt-4.1, ít khác biệt'),
    dict(id='gpt-5', price=(1.25, 10.00), think=True, use='Tốt nhất · nội dung khó, nhiều thuật ngữ; chậm và đắt nhất'),
]
WHISPER_PER_MINUTE = 0.006


def ai_texts_wanted(settings):
    return bool(settings.get('design')) and 'ai' in (settings['title_source'], settings['body_source'])


def words_for(chars):
    """About how many Vietnamese words fit in that many characters (a word is ~4.5 letters + a space)."""
    return max(1, int(chars / 5.5))


def text_rules(settings):
    """Title/body rules for the same OpenAI call that writes the voice text (no extra request). Models count
    characters badly, so the limit is also given in words and the target is set a little under the maximum."""
    t, lo, hi = settings['title_chars'], settings['body_min_chars'], settings['body_max_chars']
    return (f'\n- Ngoài lời đọc, viết thêm TIÊU ĐỀ (title) và NỘI DUNG (body) để hiện chữ trên khung video.'
            f'\n- GIỚI HẠN BẮT BUỘC, tính cả dấu cách và dấu câu: title TỐI ĐA {t} ký tự (khoảng {words_for(t)} từ, nhắm khoảng {round(t * .85)} ký tự); '
            f'body từ {lo} đến {hi} ký tự (khoảng {words_for(lo)}–{words_for(hi)} từ, 1–2 câu ngắn, nhắm khoảng {round((lo + hi) / 2)} ký tự).'
            '\n- Trước khi trả lời, tự đếm số ký tự của title và body; nếu vượt giới hạn thì viết lại ngắn hơn. Thà ngắn hơn một chút còn hơn vượt. '
            'Title là một cụm hoàn chỉnh (không kết thúc bằng "và", "cho", "của", "với", "để"…); body kết thúc bằng câu hoàn chỉnh.'
            '\n- Tiếng Việt tự nhiên, hấp dẫn, nêu lợi ích chính; không hashtag, không emoji, không ngoặc kép, không xuống dòng. Áp dụng đúng các quy tắc nội dung bên trên.')


NAME_RULE = ('\n- Thêm trường file_name: tên file cho video, gọi đúng sản phẩm đang được giới thiệu, tiếng Việt KHÔNG DẤU, chữ thường, '
             'các từ nối bằng dấu gạch ngang, dài 15–30 ký tự (khoảng 3–6 từ), không đuôi .mp4, không giá, không thương hiệu. '
             'Ví dụ: quan-ao-nu-hottrend, noi-chien-khong-dau-mini.')


NAME_FIELD = dict(type='string', description='Tên file 15–30 ký tự, không dấu, chữ thường, nối bằng dấu gạch ngang, theo sản phẩm')


def slug_name(text):
    """quan-ao-nu-hottrend: lower case, no accents, words joined by '-', at most 30 characters (cut between words)."""
    text = unicodedata.normalize('NFD', str(text or '').replace('đ', 'd').replace('Đ', 'D'))
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn').lower()
    text = re.sub(r'[^a-z0-9]+', '-', text).strip('-')
    if len(text) > 30:
        cut = text[:31].rfind('-')
        text = text[:cut] if cut >= 15 else text[:30]
    return text.rstrip('-')


def set_file_name(job, raw):
    """The video's name from the AI (same call as the translation): used for the queue and the exported file."""
    name = slug_name(raw.get('file_name')) if isinstance(raw, dict) else ''
    if len(name) >= 3:
        job['file_name'] = name


def text_schema(settings):
    t, lo, hi = settings['title_chars'], settings['body_min_chars'], settings['body_max_chars']
    return dict(title=dict(type='string', description=f'Tiêu đề, tối đa {t} ký tự kể cả dấu cách'),
                body=dict(type='string', description=f'Nội dung, {lo}–{hi} ký tự kể cả dấu cách, câu hoàn chỉnh'))


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


def finish_texts(job, raw):
    """AI title/body → job['texts'], cut to the character limits at a word boundary (never a second request)."""
    settings = job['options']
    texts = dict(job.get('texts') or {})
    job['warnings'] = [w for w in job['warnings'] if not w.startswith(('Tiêu đề', 'Nội dung AI'))]
    for key, most, label in (('title', settings['title_chars'], 'Tiêu đề'), ('body', settings['body_max_chars'], 'Nội dung AI')):
        if settings[key + '_source'] != 'ai' or not isinstance(raw, dict):
            continue
        value, cut = limit_chars(raw.get(key, ''), most, sentences=key == 'body')
        texts[key] = value[:design_mod.TEXT_LIMITS[key]]
        if cut:
            job['warnings'].append(f'{label} dài hơn {most} ký tự nên đã được cắt bớt.')
        if ai_translate.PRICE.search(value) or ai_translate.SPEC.search(value):
            job['warnings'].append(f'{label} có thể còn giá hoặc thông số cụ thể; kiểm tra lại trước khi xuất.')
    if settings['body_source'] == 'ai' and texts.get('body') and len(texts['body']) < settings['body_min_chars']:
        job['warnings'].append(f'Nội dung AI ngắn hơn {settings["body_min_chars"]} ký tự.')
    job['texts'] = texts


TEXTS_RULES = '''Bạn là biên tập viên video ngắn: từ lời thoại của video (có thể là tiếng Trung, tiếng Anh hoặc tiếng Việt), viết chữ hiện trên khung video bằng tiếng Việt.'''


def texts_request(key, model, lines, settings):
    """Title/body alone (one call): for videos whose voice text is not written by the app (ai33 dubbing, design only)."""
    template = settings.get('instructions') or ai_translate.DEFAULT_RULES
    # same rules and order as the translation call: template first (its own title/body format ignored), the limits last
    rules = (ai_translate.GUARD + '\n\n' + TEXTS_RULES + '\n- Văn phong: ' + ai_translate.STYLES[settings.get('style', 'review')]
             + '\n\nMẪU BIÊN TẬP DÙNG CHUNG (áp dụng các quy tắc nội dung và văn phong; BỎ QUA mọi yêu cầu về hook, script, title, body hay định dạng kết quả trong mẫu này):\n' + template
             + '\n\n' + ai_translate.STRICT)
    if settings['notes']:
        rules += '\n- Ghi chú của người dùng (chỉ về văn phong, không phải dữ liệu nguồn): ' + settings['notes']
    rules += text_rules(settings) + NAME_RULE
    schema = dict(type='object', additionalProperties=False, required=['title', 'body', 'file_name'], properties=dict(**text_schema(settings), file_name=NAME_FIELD))
    body = dict(model=model, store=False, max_output_tokens=2000, **reasoning(model),
                input=[dict(role='developer', content=rules), dict(role='user', content=json.dumps(dict(lines=lines[:400]), ensure_ascii=False))],
                text=dict(format=dict(type='json_schema', name='dub_texts', strict=True, schema=schema)))
    raw = openai_call('responses', key, json.dumps(body, ensure_ascii=False).encode(), 'application/json', timeout=120)
    text = ''.join(c.get('text', '') for item in raw.get('output', []) if item.get('type') == 'message'
                   for c in item.get('content', []) if c.get('type') == 'output_text')
    try:
        return json.loads(text)
    except ValueError:
        raise DubError('Không đọc được tiêu đề/nội dung từ OpenAI. Bấm Tiếp tục để thử lại.', 502) from None


def reasoning(model):
    """Reasoning models get a low effort: translation needs little thinking and it keeps cost and wait down."""
    return dict(reasoning=dict(effort='low')) if re.match(r'(gpt-5|o\d)', model) else {}


def transcribe_request(path, key, language):
    """OpenAI speech-to-text with segment timestamps."""
    fields = [('model', 'whisper-1'), ('response_format', 'verbose_json'), ('timestamp_granularities[]', 'segment')]
    if language == 'zh':
        fields += [('language', 'zh'), ('prompt', '以下是普通话的句子，使用简体中文和标点符号。')]
    elif language == 'en':
        fields += [('language', 'en')]
    body, content_type = multipart(fields, 'file', 'audio.mp3', Path(path).read_bytes(), 'audio/mpeg')
    return openai_call('audio/transcriptions', key, body, content_type, timeout=600)


TRANSLATE_RULES = '''Bạn là biên dịch viên lồng tiếng video ngắn, dịch lời thoại {src} sang tiếng Việt để đọc thành giọng nói khớp với hình.
- Dịch tự nhiên, khẩu ngữ, dễ nghe như người Việt nói; giữ đúng nghĩa, sự thật, tên riêng, đơn vị. Không thêm thông tin, không bình luận.
- MỖI DÒNG chỉ dịch dòng đó (giữ đúng id), đọc vừa trong thời gian của dòng: không vượt max_syllables tiếng (âm tiết). Nếu dòng gốc dài, lược ý phụ, giữ ý chính; câu bị cắt ngang giữa hai dòng thì dịch sao cho nối liền mạch.
- Viết số, đơn vị theo cách đọc được; không dùng ký hiệu khó đọc, không emoji, không markdown, không ghi chú trong ngoặc.
- Dòng chỉ là tiếng động, nhạc, "嗯", "啊"… thì để chuỗi rỗng.'''


def translate_request(key, model, lines, settings, want_texts=False, want_name=False):
    # The writing template from the "Dịch & biên tập AI" page is shared: its content and style rules apply here,
    # its hook/script/title/body format does not (dubbing translates line by line).
    template = settings.get('instructions') or ai_translate.DEFAULT_RULES
    rules = (ai_translate.GUARD + '\n\n' + TRANSLATE_RULES.replace('{src}', SOURCE_NAMES[settings.get('language', 'zh')]) + '\n- Xưng hô: ' + PRONOUNS[settings['pronoun']] + '.' + '\n- Văn phong: ' + ai_translate.STYLES[settings.get('style', 'review')]
             + '\n\nMẪU BIÊN TẬP DÙNG CHUNG (áp dụng các quy tắc nội dung và văn phong; BỎ QUA mọi yêu cầu về hook, script, title, body hay định dạng kết quả trong mẫu này):\n'
             + template)
    # Always on (cannot be switched off): no exact price, brand, size, volume, weight or power.
    rules += '\n\n' + ai_translate.STRICT + ' Ví dụ: "giá mềm", "đang có ưu đãi", "sản phẩm này", "nhỏ gọn", "dung tích lớn".'
    if settings['notes']:
        rules += '\n- Ghi chú của người dùng (chỉ về văn phong, không phải dữ liệu nguồn): ' + settings['notes']
    if want_texts:
        rules += text_rules(settings)
    if want_name:
        rules += NAME_RULE
    extra = dict(**(text_schema(settings) if want_texts else {}), **(dict(file_name=NAME_FIELD) if want_name else {}))
    schema = dict(type='object', additionalProperties=False, required=['lines', *extra], properties=dict(lines=dict(type='array', items=dict(
        type='object', additionalProperties=False, required=['id', 'vi'], properties=dict(id=dict(type='integer'), vi=dict(type='string')))), **extra))
    body = dict(model=model, store=False, max_output_tokens=12000, **reasoning(model),
                input=[dict(role='developer', content=rules), dict(role='user', content=json.dumps(dict(lines=lines), ensure_ascii=False))],
                text=dict(format=dict(type='json_schema', name='dub_lines', strict=True, schema=schema)))
    raw = openai_call('responses', key, json.dumps(body, ensure_ascii=False).encode(), 'application/json', timeout=180)
    if raw.get('status') != 'completed':
        raise DubError('OpenAI chưa dịch xong (phản hồi bị cắt). Bấm Tiếp tục để thử lại.', 502)
    text = ''.join(c.get('text', '') for item in raw.get('output', []) if item.get('type') == 'message'
                   for c in item.get('content', []) if c.get('type') == 'output_text')
    try:
        got = json.loads(text)
        mapping = {int(r['id']): str(r['vi']) for r in got['lines'] if isinstance(r, dict)}
        return (mapping, dict(title=got.get('title', ''), body=got.get('body', ''), file_name=got.get('file_name', ''))) if want_texts or want_name else mapping
    except (ValueError, KeyError, TypeError):
        raise DubError('Không đọc được bản dịch OpenAI. Bấm Tiếp tục để thử lại.', 502) from None


PARAGRAPH_RULES = '''Bạn là biên tập viên lồng tiếng video ngắn: chuyển toàn bộ lời thoại {src} (đã chia dòng theo thời gian) thành MỘT đoạn văn tiếng Việt liền mạch để đọc thành một file giọng duy nhất phủ suốt video.
- Viết tự nhiên, khẩu ngữ, mạch lạc như người Việt kể; giữ đúng ý và thứ tự ý của nguồn, nối câu bằng từ chuyển ý; có thể gộp hoặc lược ý phụ, không thêm thông tin.
- Độ dài: không vượt max_syllables tiếng (âm tiết) để đọc vừa thời gian seconds; ưu tiên giữ ý chính khi phải rút gọn.
- Chia câu rõ ràng bằng dấu chấm/phẩy để giọng đọc ngắt nghỉ tự nhiên; không xuống dòng, không đánh số, không markdown, không emoji, không chú thích trong ngoặc; số và đơn vị viết theo cách đọc được.'''


def paragraph_request(key, model, segments, seconds, limit, settings):
    """Whole video → one natural Vietnamese paragraph (one ai33 file)."""
    template = settings.get('instructions') or ai_translate.DEFAULT_RULES
    rules = (ai_translate.GUARD + '\n\n' + PARAGRAPH_RULES.replace('{src}', SOURCE_NAMES[settings.get('language', 'zh')]) + '\n- Xưng hô: ' + PRONOUNS[settings['pronoun']] + '.' + '\n- Văn phong: ' + ai_translate.STYLES[settings.get('style', 'review')]
             + '\n\nMẪU BIÊN TẬP DÙNG CHUNG (áp dụng các quy tắc nội dung và văn phong; BỎ QUA mọi yêu cầu về hook, script, title, body hay định dạng kết quả trong mẫu này):\n'
             + template)
    # Always on (cannot be switched off): no exact price, brand, size, volume, weight or power.
    rules += '\n\n' + ai_translate.STRICT + ' Ví dụ: "giá mềm", "đang có ưu đãi", "sản phẩm này", "nhỏ gọn", "dung tích lớn".'
    if settings['notes']:
        rules += '\n- Ghi chú của người dùng (chỉ về văn phong, không phải dữ liệu nguồn): ' + settings['notes']
    data = dict(seconds=round(seconds, 1), max_syllables=limit, lines=[dict(start=round(s['start'], 1), end=round(s['end'], 1), zh=s['zh']) for s in segments])
    want = ai_texts_wanted(settings)
    if want:
        rules += text_rules(settings)
    rules += NAME_RULE
    extra = dict(**(text_schema(settings) if want else {}), file_name=NAME_FIELD)
    schema = dict(type='object', additionalProperties=False, required=['text', *extra], properties=dict(text=dict(type='string'), **extra))
    body = dict(model=model, store=False, max_output_tokens=12000, **reasoning(model),
                input=[dict(role='developer', content=rules), dict(role='user', content=json.dumps(data, ensure_ascii=False))],
                text=dict(format=dict(type='json_schema', name='dub_paragraph', strict=True, schema=schema)))
    raw = openai_call('responses', key, json.dumps(body, ensure_ascii=False).encode(), 'application/json', timeout=180)
    if raw.get('status') != 'completed':
        raise DubError('OpenAI chưa dịch xong (phản hồi bị cắt). Bấm Tiếp tục để thử lại.', 502)
    text = ''.join(c.get('text', '') for item in raw.get('output', []) if item.get('type') == 'message'
                   for c in item.get('content', []) if c.get('type') == 'output_text')
    try:
        got = json.loads(text)
        paragraph = ' '.join(str(got['text']).split())
    except (ValueError, KeyError, TypeError):
        raise DubError('Không đọc được bản dịch OpenAI. Bấm Tiếp tục để thử lại.', 502) from None
    return dict(text=paragraph, title=got.get('title', ''), body=got.get('body', ''), file_name=got.get('file_name', ''))


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


def silence_spans(path, noise='-35dB', least=.12):
    """(start, end) of every pause in a voice file."""
    try:
        out = subprocess.run(['ffmpeg', '-hide_banner', '-nostdin', '-i', str(path), '-af', f'silencedetect=noise={noise}:d={least}', '-f', 'null', '-'],
                             capture_output=True, text=True, timeout=300).stderr
    except (OSError, subprocess.SubprocessError):
        return []
    starts = [float(x) for x in re.findall(r'silence_start: (-?[\d.]+)', out)]
    ends = [float(x) for x in re.findall(r'silence_end: ([\d.]+)', out)]
    return [(max(0.0, a), b) for a, b in zip(starts, ends) if b > a]


def split_voice(spans, weights, total):
    """Cut one voice file of `total` seconds into len(weights) sentences: the boundaries are the pauses closest to
    where each sentence should end by its length (weights = syllables), chosen in order by dynamic programming.
    Returns [(from, to)] per sentence; with too few pauses the missing cuts fall back to the length estimate."""
    n = len(weights)
    if n <= 1:
        return [(0.0, total)]
    spans = [s for s in spans if .05 < s[0] and s[1] < total - .05]
    whole = sum(weights) or 1
    targets, done = [], 0
    for w in weights[:-1]:
        done += w
        targets.append(total * done / whole)
    need = n - 1
    if len(spans) >= need:
        mids = [(a + b) / 2 for a, b in spans]
        # best[i][j]: cost of placing the first i boundaries using pauses among the first j
        inf = float('inf')
        best = [[inf] * (len(mids) + 1) for _ in range(need + 1)]
        pick = [[False] * (len(mids) + 1) for _ in range(need + 1)]
        for j in range(len(mids) + 1):
            best[0][j] = 0.0
        for i in range(1, need + 1):
            for j in range(i, len(mids) + 1):
                skip = best[i][j - 1]
                # a longer pause is a likelier sentence break: it gets a small bonus
                take = best[i - 1][j - 1] + abs(mids[j - 1] - targets[i - 1]) - min(.3, spans[j - 1][1] - spans[j - 1][0])
                best[i][j], pick[i][j] = (take, True) if take < skip else (skip, False)
        chosen, i, j = [], need, len(mids)
        while i:
            if pick[i][j]:
                chosen.append(spans[j - 1])
                i -= 1
            j -= 1
        cuts = list(reversed(chosen))
    else:
        cuts = [(t, t) for t in targets]
    out, at = [], 0.0
    for a, b in cuts:
        out.append((at, a))
        at = b
    out.append((at, total))
    return out


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

def run(cmd, cancel=None, timeout=7200, cwd=None, name='FFmpeg'):
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
            raise DubError(name + ' xử lý lỗi: ' + err.decode('utf-8', 'replace').strip()[-300:])


def probe(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_type,codec_name,width,height,channels,pix_fmt,sample_rate',
                          '-of', 'json', str(path)], capture_output=True, text=True, timeout=30)
    data = json.loads(out.stdout or '{}')
    streams = data.get('streams', [])
    video = next((s for s in streams if s.get('codec_type') == 'video'), {})
    audio = next((s for s in streams if s.get('codec_type') == 'audio'), None)
    return dict(duration=float(data.get('format', {}).get('duration', 0) or 0), video=video, audio=audio)


def native_rate(path):
    """Sample rate of an MP3/WAV voice, kept as it is (16–48 kHz) instead of 24 kHz."""
    try:
        rate = int(float((probe(path)['audio'] or {}).get('sample_rate') or 0))
    except (OSError, ValueError, subprocess.SubprocessError):
        rate = 0
    return min(48000, rate) if rate >= 16000 else VOICE_RATE


def balance(voice, room, lo, hi, fast, slow, shorten=True):
    """Voice tempo and video stretch so that voice / tempo == room * stretch, the gap split between both
    (equal steps, so neither changes much); each stays in its limits and whatever is left is cut later.
    shorten=False keeps the whole video when the voice is the shorter one."""
    ratio = voice / room
    if abs(ratio - 1) < .01 or (ratio < 1 and not shorten):
        return 1.0, 1.0
    tempo = min(hi, max(lo, math.sqrt(ratio)))
    stretch = min(slow, max(fast, ratio / tempo))
    tempo = min(hi, max(lo, ratio / stretch))   # the video reached its limit: the voice takes what is left
    return tempo, stretch


def mix_voice(groups, folder, duration, rate=VOICE_RATE):
    """Write voice.wav (mono, 24 kHz or the MP3's own rate) with every fitted clip copied in at its start time."""
    total = int(math.ceil(duration * rate)) * 2
    buffer = bytearray(total)
    for g in groups:
        if not g.get('raw'):
            continue
        data = (folder / g['raw']).read_bytes()
        at = int(g.get('place', g['start']) * rate) * 2
        data = data[:max(0, total - at)]
        buffer[at:at + len(data)] = data
    with wave.open(str(folder / 'voice.wav'), 'wb') as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
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


def design_video(design, W, H, stretch=1, duration=0, adjust=()):
    """With a design the video sits in the design's video box exactly as in the editor (x/y/width/height/zoom in
    720×1280 design pixels, cover/contain/stretch, camera zoom in/out over the video, flip, rotation) on the
    background colour → [framed]."""
    scale = W / design_mod.W
    box = design_mod.video_box(design)
    vw, vh = max(2, round(box['width'] * scale / 2) * 2), max(2, round(box['height'] * scale / 2) * 2)
    chain = '[0:v:0]' + (f'setpts=PTS*{stretch:.6f},' if stretch != 1 else '') + 'fps=30,' + ''.join(a + ',' for a in adjust) + 'format=rgba,'
    fit = design.get('video_fit', 'cover')
    if fit == 'cover':
        chain += f'scale={vw}:{vh}:force_original_aspect_ratio=increase,crop={vw}:{vh},'
    elif fit == 'contain':
        chain += f'scale={vw}:{vh}:force_original_aspect_ratio=decrease,pad={vw}:{vh}:(ow-iw)/2:(oh-ih)/2:color=0x00000000,'
    else:
        chain += f'scale={vw}:{vh},'
    motion, amount = design.get('video_motion', 'none'), design.get('motion_amount', 12)
    if motion in ('zoom_in', 'zoom_out') and isinstance(amount, (int, float)) and 0 < amount <= 50 and duration > 0:
        # "Hiệu ứng máy quay": the picture grows (or shrinks back) by amount % over the video, cropped to its box
        k = amount / 100
        grow = f'(1+{k}*t/{duration:.3f})' if motion == 'zoom_in' else f'(1+{k}*(1-t/{duration:.3f}))'
        chain += (f"scale=w='trunc({vw}*{grow}/2)*2':h='trunc({vh}*{grow}/2)*2':eval=frame,"
                  f"crop={vw}:{vh}:x='(iw-{vw})/2':y='(ih-{vh})/2',")
    flip = design.get('video_flip', 'none')
    chain += ('hflip,' if 'h' in flip else '') + ('vflip,' if 'v' in flip else '')
    rad = math.radians(float(design.get('video_rotation', 0)))
    chain += f'rotate={rad:.12f}:ow=rotw({rad:.12f}):oh=roth({rad:.12f}):c=none,setsar=1[clip]'
    color = '0x000000' if design.get('background') == 'none' else design['color'].replace('#', '0x')
    x, y = box['x'] * scale, box['y'] * scale
    return [chain, f'color=c={color}:s={W}x{H}:r=30,format=rgba[dbase]',
            f'[dbase][clip]overlay=x={x}+({vw}-overlay_w)/2:y={y}+({vh}-overlay_h)/2:shortest=1:format=auto[framed]']


def frame_identity(settings):
    return (settings.get('frame_canvas', 'source') == 'source' and settings.get('frame_zoom', 100) == 100 and not settings.get('frame_x')
            and not settings.get('frame_y') and not settings.get('frame_rotate') and settings.get('frame_flip', 'none') == 'none')


def adjust_filters(settings):
    """"Điều chỉnh" of the source video (like CapCut): brightness, contrast, saturation (eq) and sharpen (unsharp).
    -100..100 (sharpen 0..100); 0 = unchanged. The CSS preview uses the same scale."""
    if not settings.get('adjust'):   # the switch of the section is off: the values are kept for later
        return []
    b, c, sat, sharp = (settings.get('adjust_' + k, 0) or 0 for k in ('brightness', 'contrast', 'saturation', 'sharpen'))
    out = []
    if b or c or sat:
        out.append(f'eq=brightness={b / 100 * .25:.4f}:contrast={1 + c / 100 * .5:.4f}:saturation={1 + sat / 100:.4f}')
    if sharp:
        out.append(f'unsharp=5:5:{sharp / 100 * 1.5:.3f}:5:5:0')
    return out


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


# CapCut-style blend modes for the image layer → FFmpeg blend modes (the browser preview uses the CSS equivalents)
IMAGE_BLENDS = {'normal': None, 'darken': 'darken', 'multiply': 'multiply', 'burn': 'burn', 'lighten': 'lighten', 'screen': 'screen',
                'dodge': 'dodge', 'addition': 'addition', 'overlay': 'overlay', 'softlight': 'softlight', 'hardlight': 'hardlight',
                'difference': 'difference', 'exclusion': 'exclusion'}
IMAGE_TYPES = ('.png', '.jpg', '.jpeg', '.webp')


def image_chain(index, settings, W, H, base, duration):
    """Graph lines putting the still image (input `index`, looped for `duration`) on [base]. Size is a share of the
    frame (image_w % of width, image_h % of height; image_h 0 = keep the picture's ratio), centre offset image_x/y %
    of the frame, then flip, rotate, opacity and blend mode. Blend modes use the picture's own alpha as the mask."""
    w = max(2, round(W * settings['image_w'] / 100 / 2) * 2)
    h = max(2, round(H * settings['image_h'] / 100 / 2) * 2) if settings['image_h'] else -2
    chain = f'[{index}:v]format=rgba,scale={w}:{h}'
    chain += {'none': '', 'h': ',hflip', 'v': ',vflip', 'hv': ',hflip,vflip'}[settings['image_flip']]
    if settings['image_rotate']:
        turn = math.radians(settings['image_rotate'])
        chain += f',rotate={turn:.9f}:ow=rotw({turn:.9f}):oh=roth({turn:.9f}):c=none'
    chain += f",colorchannelmixer=aa={settings['image_opacity'] / 100:.3f}[im]"
    x = f"main_w*{.5 + settings['image_x'] / 100:.5f}-overlay_w/2"
    y = f"main_h*{.5 + settings['image_y'] / 100:.5f}-overlay_h/2"
    mode = IMAGE_BLENDS[settings['image_blend']]
    if not mode:
        return [chain, f'[{base}][im]overlay=x={x}:y={y}:format=auto:eof_action=repeat[img]'], 'img'
    return [chain, f'color=c=black@0:s={W}x{H}:r=30:d={duration:.3f},format=rgba[icv]',
            f'[icv][im]overlay=x={x}:y={y}:format=auto:eof_action=repeat[ilay]', '[ilay]split[ilc][ila]', '[ila]alphaextract[imask]',
            f'[{base}]split[ib1][ib2]', '[ib1]format=gbrp[ibg]', '[ilc]format=gbrp[ilg]',
            f'[ibg][ilg]blend=all_mode={mode}:shortest=1,format=rgba[ibl]', '[ibl][imask]alphamerge[ibm]',
            '[ib2][ibm]overlay=0:0:format=auto:shortest=1[img]'], 'img'


ALPHA_FORMATS = re.compile(r'^(yuva|rgba|bgra|argb|abgr|gbrap|ya|pal8)')
BROWSER_VIDEO = ('h264', 'vp8', 'vp9', 'av1')


def overlay_alpha(path):
    """(has transparency, codec) — ProRes 4444/QuickTime Animation/PNG MOV, PNG/GIF/WebP and WebM with an alpha channel."""
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=codec_name,pix_fmt:stream_tags',
                          '-of', 'json', str(path)], capture_output=True, text=True, timeout=30)
    try:
        stream = (json.loads(out.stdout or '{}').get('streams') or [{}])[0]
    except ValueError:
        stream = {}
    tags = {k.lower(): str(v) for k, v in (stream.get('tags') or {}).items()}
    codec = stream.get('codec_name') or ''
    return bool(ALPHA_FORMATS.match(stream.get('pix_fmt') or '') or tags.get('alpha_mode') == '1'), codec


def overlay_decoder(meta):
    """FFmpeg's own VP8/VP9 decoders drop the alpha layer of WebM; libvpx keeps it."""
    if meta.get('alpha') and meta.get('codec') in ('vp8', 'vp9'):
        return ['-c:v', 'libvpx' if meta['codec'] == 'vp8' else 'libvpx-vp9']
    return []


def overlay_fit(W, H):
    return f'fps=30,scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1'


def overlay_chain(source, item, W, H, settings, base, duration):
    """Graph lines putting an overlay stream (`source`: an input like [3:v] or a joined sequence label) on top of
    [base]; returns (lines, new label). Longer than the video → cut to the video; shorter → looped or joined
    (decided by the inputs). normal/key: alpha overlay (key removes a green background) · screen: blend for effects on black.
    Files with their own transparency (item['alpha']) always use the normal alpha overlay, full frame."""
    op = settings['overlay_opacity'] / 100
    k = item['k']
    random_time = settings['overlay_timing'] == 'random'
    chain = f'{source}{overlay_fit(W, H)}' + ('' if random_time else f',trim=duration={duration:.3f},setpts=PTS-STARTPTS')
    blend = 'normal' if item.get('alpha') else settings['overlay_blend']
    if blend == 'screen':
        if random_time:
            chain += f",tpad=start_duration={item['start']:.3f}:stop_duration={duration + 5:.3f}:color=black"
        return [chain + f',format=gbrp[ov{k}]', f'[{base}]format=gbrp[bk{k}]',
                f'[bk{k}][ov{k}]blend=all_mode=screen:all_opacity={op:.3f}:shortest=1[os{k}]'], f'os{k}'
    if blend == 'key':
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
        self.running = 0
        try:
            self.parallel = parallel_count(json.loads((self.root / 'queue.json').read_text(encoding='utf-8')).get('parallel'))
        except (OSError, ValueError, AttributeError, DubError):
            self.parallel = 1
        for _ in range(MAX_PARALLEL):
            threading.Thread(target=self.worker, daemon=True).start()

    def set_parallel(self, value):
        """How many videos are processed at the same time (the steps of one job stay in order)."""
        with self.lock:
            self.parallel = parallel_count(value)
            (self.root / 'queue.json').write_text(json.dumps(dict(parallel=self.parallel)), encoding='utf-8')
        self.wake.set()
        return self.queue_info()

    def queue_info(self):
        return dict(parallel=self.parallel, max=MAX_PARALLEL, running=self.running, waiting=len(self.queue))

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
        return {k: job.get(k) for k in ('id', 'name', 'file_name', 'state', 'step', 'steps', 'progress', 'message', 'created', 'outputs', 'warnings', 'duration', 'video_id')} | \
               dict(texts=self.texts_for(job) if job.get('options', {}).get('design') else None, mp3=bool(job.get('mp3')), mode=job.get('options', {}).get('mode', 'lines'), lines=len(job.get('segments') or []), translated=len(job.get('segments') or []) if job.get('paragraph') else sum(1 for s in job.get('segments') or [] if s.get('vi')))

    def jobs(self):
        # summaries are cached by job.json's modification time: hundreds of finished jobs stay cheap to list
        rows, cache = [], self.__dict__.setdefault('_summaries', {})
        for folder in self.root.iterdir():
            meta = folder / 'job.json'
            if folder.is_dir() and re.fullmatch('[a-f0-9]{32}', folder.name) and meta.is_file():
                try:
                    stamp = meta.stat().st_mtime_ns
                    if folder.name in self.live or cache.get(folder.name, (None,))[0] != stamp:
                        cache[folder.name] = (stamp, self.summary(self.load(folder.name)))
                    rows.append(cache[folder.name][1])
                except (DubError, OSError):
                    pass
        return sorted(rows, key=lambda r: r.get('created') or '', reverse=True)

    # -- commands
    def create(self, raw):
        ids = raw.get('video_ids')
        if not isinstance(ids, list) or not 1 <= len(ids) <= 1000:
            raise DubError('Chọn từ 1 đến 1000 video để lồng tiếng.')
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
            mp3 = (raw.get('mp3') or {}).get(vid) if isinstance(raw.get('mp3'), dict) else None
            if mp3:
                job['mp3'] = self.attach_mp3(self.root / key, mp3)
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

    def attach_mp3(self, folder, ref):
        """MP3/WAV for a video: a file on this computer (hard link or copy) or an audio of the library by id."""
        if isinstance(ref, str) and re.fullmatch('[a-f0-9]{32}', ref) and (self.audio_dir / (ref + '.mp3')).is_file():
            src = self.audio_dir / (ref + '.mp3')
        else:
            src = Path(ref) if isinstance(ref, str) and len(ref) < 1000 else None
            if not src or not src.is_absolute() or not src.is_file() or src.suffix.lower() not in ('.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg'):
                raise DubError('Không đọc được file âm thanh cho video.')
        target = folder / ('voice-src' + src.suffix.lower())
        try:
            os.link(src, target)
        except OSError:
            shutil.copyfile(src, target)
        return target.name

    def enqueue(self, key, raw):
        job = self.load(key)
        settings = job['options']
        keys = dict(openai=openai_key(raw), ai33=ai33_key(raw))
        pending = any(job['steps'][s] not in ('done', 'skipped') for s in ('asr', 'translate'))
        need_openai = (pending and (ai_texts_wanted(settings) if settings['mode'] == 'design' else settings['mode'] != 'ai33')) or bool(job.get('texts_redo'))
        if need_openai and not keys['openai']:
            raise DubError('Nhập OpenAI API key (dùng cho nhận diện giọng và dịch/viết chữ). Không gửi key trong chat.')
        if settings['mode'] != 'design':
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
        if start == 'texts':
            # rewrite only the title/body (one OpenAI call) and export again; the voice already made is kept
            job.pop('texts', None)
            job.pop('texts_manual', None)
            job['texts_redo'] = True
            job['steps']['export'] = 'pending'
            job['outputs'] = {}
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
        job['texts_passed'] = start != 'texts'   # rewritten texts wait for review again
        self.save(job)
        self.enqueue(key, raw)
        return self.load(key)

    def review(self, raw):
        """Review table: save the title/body typed for each job and export them (no AI call)."""
        items = raw.get('items')
        if not isinstance(items, list) or not 1 <= len(items) <= 1000:
            raise DubError('Danh sách duyệt chữ không hợp lệ.')
        done, errors = 0, []
        for item in items:
            try:
                if not isinstance(item, dict):
                    raise DubError('Dòng không hợp lệ.')
                key = item.get('id')
                job = self.load(key)
                if job['state'] != 'review':
                    raise DubError('Không ở trạng thái chờ duyệt.')
                if 'title' in item or 'body' in item:
                    now = self.texts_for(job)
                    texts = dict(title=item.get('title', now.get('title', '')), body=item.get('body', now.get('body', '')))
                    if texts != {k: now.get(k, '') for k in ('title', 'body')}:
                        self.edit_texts(key, texts)
                self.proceed(key, {k: v for k, v in raw.items() if k != 'items'})
                done += 1
            except DubError as exc:
                errors.append(dict(id=item.get('id') if isinstance(item, dict) else None, error=str(exc)))
        return dict(done=done, errors=errors)

    def estimate(self, raw):
        """Durations for the check before a run: library videos from their metadata, files on this computer probed."""
        ids, paths = raw.get('ids') or [], raw.get('paths') or []
        if not isinstance(ids, list) or not isinstance(paths, list) or len(ids) + len(paths) > 1000:
            raise DubError('Danh sách video không hợp lệ.')
        out = {}
        for vid in ids:
            try:
                out[vid] = float(json.loads((self.video_dir / vid / 'source.json').read_text(encoding='utf-8'))['duration']) \
                    if isinstance(vid, str) and re.fullmatch('[a-f0-9]{32}', vid) else None
            except (OSError, ValueError, KeyError, TypeError):
                out[vid] = None
        def one(p):
            path = Path(p) if len(p) < 1000 else None
            if not path or not path.is_absolute() or not path.is_file() or path.suffix.lower() not in ('.mp4', '.mov', '.m4v', '.mkv', '.webm', '.avi'):
                return p, None
            try:
                return p, probe(path)['duration'] or None
            except (OSError, ValueError, subprocess.SubprocessError):
                return p, None
        with ThreadPoolExecutor(8) as pool:
            out.update(dict(pool.map(one, [p for p in paths if isinstance(p, str)])))
        return dict(durations=out)

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

    def edit_texts(self, key, raw):
        """Title/body typed in the queue: replace this video's texts and export again (no AI call)."""
        job = self.load(key)
        if job['state'] in ('running', 'queued'):
            raise DubError('Dừng tác vụ trước khi sửa chữ.')
        if not job['options'].get('design'):
            raise DubError('Tác vụ này không dùng thiết kế có chữ.')
        texts = {}
        for k in ('title', 'body'):
            v = raw.get(k, '') if isinstance(raw, dict) else ''
            if not isinstance(v, str) or len(v) > design_mod.TEXT_LIMITS[k]:
                raise DubError('Chữ quá dài.')
            texts[k] = ' '.join(v.split()) if k == 'title' else v.strip()
        job['texts_manual'] = texts
        job['steps']['export'] = 'pending'
        job['outputs'] = {}
        if job['state'] == 'done':
            job['state'] = 'review'
            job['message'] = 'Đã sửa chữ. Bấm Tiếp tục để xuất lại video.'
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
            with self.lock:
                key = self.queue.pop(0) if self.queue and self.running < self.parallel else None
                if key:
                    self.running += 1
                if not self.queue or self.running >= self.parallel:
                    self.wake.clear()
            if key:
                try:
                    self.run_job(key)
                finally:
                    with self.lock:
                        self.running -= 1
                    self.wake.set()

    def run_job(self, key):
        job = self.load(key)
        cancel = self.cancels.get(key) or threading.Event()
        if cancel.is_set():
            return
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

        if settings['mode'] == 'design':
            # Dựng video: no translation; recognition only when the AI writes the title/body from what is said
            if not (ai_texts_wanted(settings) and info['audio'] and keys.get('openai')):
                for step in ('asr', 'translate'):
                    if job['steps'][step] not in ('done', 'skipped'):
                        job['steps'][step] = 'skipped'
                if ai_texts_wanted(settings) and not job.get('texts'):
                    job['warnings'] = [w for w in job['warnings'] if not w.startswith('Chữ AI')] + ['Chữ AI cần video có tiếng và OpenAI key; đã dùng tên file cho tiêu đề.']
        if settings['mode'] == 'ai33':
            # ai33.pro /v1/task/dubbing recognises, translates and times the voice itself
            for step in ('asr', 'translate'):
                if job['steps'][step] != 'done':
                    job['steps'][step] = 'skipped'
        if job['steps']['asr'] not in ('done', 'skipped'):
            if not info['audio']:
                raise DubError('Video không có âm thanh để nhận diện. Hãy nhập SRT lời gốc có sẵn.')
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

        if job['steps']['translate'] not in ('done', 'skipped') and settings['mode'] == 'design':
            job.pop('texts_manual', None)
            self.progress(job, 'translate', .3, 'Đang viết tiêu đề và nội dung (OpenAI)…')
            self.save(job)
            got = texts_request(keys['openai'], settings['model'], [s['zh'] for s in job['segments']], settings)
            finish_texts(job, got)
            set_file_name(job, got)
            self.finish(job, 'translate')
        if job['steps']['translate'] != 'done' and settings['mode'] == 'paragraph':
            start, seconds = paragraph_window(job)
            limit = max(4, int(seconds * settings['rate']))
            self.progress(job, 'translate', .3, 'Đang dịch thành đoạn văn tiếng Việt…')
            self.save(job)
            text = paragraph_request(keys['openai'], settings['model'], job['segments'], seconds, limit, settings)
            if isinstance(text, dict):   # the same call also wrote the title/body and the file name
                if ai_texts_wanted(settings):
                    finish_texts(job, text)
                set_file_name(job, text)
                text = text['text']
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
        if job['steps']['translate'] not in ('done', 'skipped'):
            pending = [i for i, s in enumerate(job['segments']) if 'vi' not in s]
            for n in range(0, len(pending), 40):
                batch = pending[n:n + 40]
                self.progress(job, 'translate', n / max(1, len(pending)), f'Đang dịch sang tiếng Việt ({n}/{len(pending)} câu)…')
                self.save(job)
                lines = [dict(id=i, seconds=round(job['segments'][i]['end'] - job['segments'][i]['start'], 2),
                              max_syllables=budget(job['segments'][i], settings['rate']), zh=job['segments'][i]['zh'],
                              before=job['segments'][i - 1]['zh'] if i else '') for i in batch]
                want = n == 0 and ai_texts_wanted(settings) and not job.get('texts')
                if want or (n == 0 and not job.get('file_name')):
                    # the first batch also writes the title/body and the video's file name (same call)
                    got = translate_request(keys['openai'], settings['model'], lines, settings, want_texts=want, want_name=True)
                    got, texts = got if isinstance(got, tuple) else (got, {})
                    if want:
                        finish_texts(job, texts)
                    set_file_name(job, texts)
                else:
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
            if settings['mode'] == 'ai33':
                self.dub_ai33(job, folder, source, info, keys, cancel)
                if ai_texts_wanted(settings) and not job.get('texts'):
                    if keys.get('openai'):
                        got = texts_request(keys['openai'], settings['model'], [s['vi'] for s in job['segments'] if s.get('vi')], settings)
                        finish_texts(job, got)
                        set_file_name(job, got)
                    else:
                        job['warnings'].append('Chữ AI cần OpenAI key; đã dùng tên file cho tiêu đề.')
            elif settings['mode'] == 'design':
                self.voice_mp3(job, folder, cancel)
            else:
                self.tts(job, folder, keys, cancel)
            self.finish(job, 'tts')
        check()

        if job['steps']['mix'] != 'done' and settings['mode'] == 'ai33':
            # already timed like the source: copied in at 0, the tail past the video is cut
            self.progress(job, 'mix', .2, 'Đang ghép giọng lồng tiếng ai33…')
            g = job['groups'][0]
            g.update(tempo=1.0, place=0, overflow=round(max(0.0, g['clip_seconds'] - job['duration']), 2), raw=g['file'].replace('.wav', '.pcm'))
            run(['ffmpeg', '-hide_banner', '-nostdin', '-y', '-i', str(folder / g['file']), '-t', f"{job['duration']:.3f}",
                 '-ac', '1', '-ar', str(job.get('voice_rate', VOICE_RATE)), '-f', 's16le', str(folder / g['raw'])], cancel)
            mix_voice(job['groups'], folder, job['duration'], job.get('voice_rate', VOICE_RATE))
            self.finish(job, 'mix')
        if job.pop('texts_redo', False) and ai_texts_wanted(settings):
            if keys.get('openai'):
                self.progress(job, 'export', .02, 'Đang viết lại tiêu đề và nội dung (OpenAI)…')
                source = [job['paragraph']] if job.get('paragraph') else [s.get('vi') or s.get('zh', '') for s in job['segments']]
                got = texts_request(keys['openai'], settings['model'], [t for t in source if t] or [job['name']], settings)
                finish_texts(job, got)
                set_file_name(job, got)
            else:
                job['warnings'].append('Viết lại chữ AI cần OpenAI key.')
        if job['steps']['mix'] != 'done' and settings['mode'] == 'design':
            self.progress(job, 'mix', .2, 'Đang ghép âm thanh…')
            if job.get('groups'):
                self.place_paragraph(job, folder, cancel)
            else:
                job['video_stretch'], job['output_duration'] = 1, job['duration']
                mix_voice([], folder, job['duration'])
            self.finish(job, 'mix')
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
                fade = f",afade=t=out:st={max(0, slot - .25):.3f}:d=0.25,atrim=duration={slot:.3f}" if g['overflow'] > .05 else ''
                run(['ffmpeg', '-hide_banner', '-nostdin', '-y', '-i', str(folder / g['file']), '-af', tempo_filter(g['tempo']) + fade,
                     '-ac', '1', '-ar', str(job.get('voice_rate', VOICE_RATE)), '-f', 's16le', str(folder / g['raw'])], cancel)
            mix_voice(job['groups'], folder, job['duration'], job.get('voice_rate', VOICE_RATE))
            self.finish(job, 'mix')
        check()

        if settings.get('review_texts') and ai_texts_wanted(settings) and not job.get('texts_passed'):
            # "Dừng lại để duyệt chữ": the AI title/body wait in the review table; nothing is exported yet
            job['state'] = 'review'
            job['step'] = 'export'
            job['message'] = 'AI đã viết tiêu đề và nội dung. Duyệt chữ rồi bấm Xuất.'
            job['progress'] = sum(WEIGHTS[s] for s in STEPS if job['steps'][s] in ('done', 'skipped'))
            return
        self.export(job, folder, source, info, cancel)
        self.finish(job, 'export')
        job['state'] = 'done'
        job['progress'] = 100
        job['message'] = ('Đã dựng xong.' if job['options']['mode'] == 'design' else 'Đã lồng tiếng xong.') + (f' Đã lưu: {job["outputs"].get("saved_path")}' if job['outputs'].get('saved_path') else '')

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
                raise DubError('Chưa cài Demucs. Bấm "Cài Demucs tự động" ở mục 🎵 Âm thanh gốc hoặc chọn cách xử lý nền khác.')
            run(base + [str(folder / 'original.wav')], cancel)
            self.progress(job, 'separate', .3, 'Đang tách giọng bằng Demucs (có thể mất vài phút)…')
            self.save(job)
            run(command + ['--two-stems=vocals', '-o', str(folder / 'demucs'), str(folder / 'original.wav')], cancel, name='Demucs')
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
        if not paragraph:
            return self.tts_one(job, folder, keys, cancel)
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
                    rate = self.voice_rate(job, download)
                    g['file'] = f'g{groups.index(g)}.wav'
                    run(['ffmpeg', '-hide_banner', '-nostdin', '-y', '-i', str(download), '-ac', '1', '-ar', str(rate), str(folder / g['file'])], cancel)
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

    frames_dir = None   # set by the app: custom PNG frames and image/logo layers of the editor
    images_dir = None

    def texts_for(self, job):
        """Title/body for this video: AI-written, the template's fixed text, the file name or nothing."""
        settings, texts = job['options'], job.get('texts') or {}
        out = dict(job['texts_manual']) if isinstance(job.get('texts_manual'), dict) else {}
        if out:
            return {k: str(out.get(k, ''))[:design_mod.TEXT_LIMITS[k]] for k in ('title', 'body')}
        for key in ('title', 'body'):
            source = settings[key + '_source']
            value = texts.get(key, '') if source == 'ai' else settings['design'].get(key, '') if source == 'fixed' else job['name'] if source == 'file' else ''
            if source == 'ai' and not value:
                value = job['name'] if key == 'title' else ''
            out[key] = str(value)[:design_mod.TEXT_LIMITS[key]]
        return out

    def design_for(self, job, folder):
        """The template's design with this video's own title/body. Text too long for its box gets smaller until it
        fits (a batch must not stop on one long title); fonts are copied next to the graph (no path escaping)."""
        opts = dict(job['options']['design'], **self.texts_for(job))
        size = {k: opts[k + '_size'] for k in ('title', 'body')}
        job['warnings'] = [w for w in job['warnings'] if not w.startswith('Chữ ')]
        for _ in range(12):
            try:
                design_mod.layout(opts)
                break
            except ValueError:
                for key in ('title', 'body'):
                    opts[key + '_size'] = max(12, round(opts[key + '_size'] * .92, 1))
        else:
            # still does not fit (e.g. the box sticks out of the canvas in the template): export anyway, say so
            opts['lenient_text'] = True
            problems = [i['warnings'][0] for i in design_mod.layout(opts, strict=False) if i['warnings']]
            job['warnings'].append('Chữ không vừa ô của mẫu dù đã thu nhỏ hết mức; video vẫn xuất. ' + (problems[0] if problems else ''))
        smaller = [f'{"tiêu đề" if k == "title" else "nội dung"} {size[k]:g}→{opts[k + "_size"]:g}px' for k in size if opts[k + '_size'] < size[k]]
        if smaller and not opts.get('lenient_text'):
            job['warnings'].append('Chữ dài nên được thu nhỏ cho vừa ô: ' + ', '.join(smaller) + '.')
        for key in design_mod.TEXT_KEYS:
            name = FONTS[opts[key + '_font']][0]
            if not (folder / name).is_file():
                shutil.copyfile(Path(__file__).resolve().parent / 'assets' / name, folder / name)
        return opts

    def voice_rate(self, job, path):
        """Keep the MP3's own sample rate. One-file modes take it from that file; per-line voices all share the
        rate of the first one (lines an older version already made at 24 kHz keep 24 kHz)."""
        if job['options']['mode'] in ('paragraph', 'design', 'ai33'):
            job['voice_rate'] = native_rate(path)
        elif 'voice_rate' not in job:
            job['voice_rate'] = VOICE_RATE if any(g.get('file') for g in job.get('groups') or []) else native_rate(path)
        return job['voice_rate']

    def voice_mp3(self, job, folder, cancel):
        """Dựng video: the video's own MP3 (same name) becomes the voice track; none = original sound only."""
        job['groups'] = []
        if not job.get('mp3') or not (folder / job['mp3']).is_file():
            return
        run(['ffmpeg', '-hide_banner', '-nostdin', '-y', '-i', str(folder / job['mp3']), '-ac', '1', '-ar', str(self.voice_rate(job, folder / job['mp3'])), str(folder / 'g0.wav')], cancel)
        with wave.open(str(folder / 'g0.wav')) as w:
            seconds = round(w.getnframes() / w.getframerate(), 3)
        job['groups'] = [dict(start=0.0, end=job['duration'], text='', lines=[], file='g0.wav', clip_seconds=seconds)]

    def tts_one(self, job, folder, keys, cancel):
        """Timestamp mode with ONE ai33 file: every translated sentence is read in a single task (one line each, so
        the voice pauses between them), then the file is cut at those pauses and each sentence goes to its own
        timestamp. Editing any sentence re-voices the whole file once (still a single task)."""
        settings = job['options']
        groups = [g for g in job['groups'] if g['text'].strip()]
        if not groups:
            raise DubError('Chưa có câu dịch nào để tạo giọng.')
        text = '\n'.join(t if re.search(r'[.!?…]$', t) else t + '.' for t in (g['text'].strip() for g in groups))
        master = job.get('master') or {}
        if master.get('text') != text:
            master = dict(text=text)
            job['master'] = master
            for g in job['groups']:
                g.pop('file', None)
        if all(g.get('file') for g in groups):
            return
        if not master.get('file'):
            if not master.get('task_id'):
                base = dict(api_key=keys['ai33'], voice_id=settings['voice_id'], speed=settings['voice_speed'], text=text, file_name=job['name'][:60])
                if settings['dictionary_id']:
                    base['pronunciation_dictionary_id'] = settings['dictionary_id']
                self.progress(job, 'tts', .05, f'Đang gửi {len(groups)} câu thành một file giọng ai33…')
                master['task_id'] = ai33_audio.create_tts(base)['task_id']
                self.save(job)
            waited = time.monotonic()
            while True:
                if cancel.is_set():
                    raise Cancelled()
                time.sleep(3)
                detail = self.poll(master, keys, job)
                if detail is None:
                    if master.get('poll_errors'):
                        job['message'] = master['poll_message']
                    continue
                if detail['status'] == 'error':
                    raise DubError('ai33.pro báo lỗi khi tạo file giọng. Kiểm tra credit/giọng rồi bấm Tiếp tục.')
                if detail['status'] == 'done' and detail['audio_url']:
                    break
                self.progress(job, 'tts', .1 + .7 * detail.get('progress', 0) / 100, f'Đang tạo một file giọng Việt ai33 ({len(groups)} câu)…')
                if time.monotonic() - waited > 900:
                    raise DubError('ai33.pro chưa trả giọng sau 15 phút. Bấm Tiếp tục để kiểm tra lại (không tạo trùng).')
            download = folder / 'master.download'
            audio_files.download(detail['audio_url'], download)
            run(['ffmpeg', '-hide_banner', '-nostdin', '-y', '-i', str(download), '-ac', '1', '-ar', str(self.voice_rate(job, download)), str(folder / 'master.wav')], cancel)
            download.unlink(missing_ok=True)
            master['file'] = 'master.wav'
            self.save(job)
        # cut at the pauses between sentences; each piece goes to the timestamp of its sentence
        self.progress(job, 'tts', .9, 'Đang cắt file giọng theo từng câu…')
        with wave.open(str(folder / master['file'])) as w:
            total = w.getnframes() / w.getframerate()
        pieces = split_voice(silence_spans(folder / master['file']), [max(1, syllables(g['text'])) for g in groups], total)
        for n, (g, (a, b)) in enumerate(zip(groups, pieces)):
            g['file'] = f'g{n}.wav'
            run(['ffmpeg', '-hide_banner', '-nostdin', '-y', '-i', str(folder / master['file']), '-ss', f'{a:.3f}', '-t', f'{max(.05, b - a):.3f}',
                 '-ac', '1', '-ar', str(job.get('voice_rate', VOICE_RATE)), str(folder / g['file'])], cancel)
            with wave.open(str(folder / g['file'])) as w:
                g['clip_seconds'] = round(w.getnframes() / w.getframerate(), 3)
        self.save(job)

    def dub_ai33(self, job, folder, source, info, keys, cancel):
        """Timestamp dubbing by ai33.pro (/v1/task/dubbing): the source audio goes up once, ai33 returns a timed
        Vietnamese SRT and, with the chosen voice, a voice-only track synthesized from that SRT. The task id is saved
        before polling, so a restart or Tiếp tục never pays twice."""
        settings = job['options']
        if not info['audio']:
            raise DubError('Video không có âm thanh để lồng tiếng.')
        g = (job.get('groups') or [None])[0]
        if not g:
            g = dict(start=0, end=job['duration'], text='', lines=[])
            job['groups'] = [g]
        if not g.get('task_id'):
            self.progress(job, 'tts', .05, 'Đang gửi âm thanh gốc lên ai33.pro để lồng tiếng theo timestamp…')
            self.save(job)
            upload = folder / 'dub-source.mp3'
            run(['ffmpeg', '-hide_banner', '-nostdin', '-y', '-i', str(source), '-vn', '-map', '0:a:0', '-ac', '2', '-ar', '44100',
                 '-c:a', 'libmp3lame', '-b:a', '128k', str(upload)], cancel)
            try:
                g['task_id'] = ai33_audio.create_dubbing(keys['ai33'], upload.read_bytes(), settings['language'], 'vi', settings['voice_id'])['task_id']
            except ValueError as exc:
                raise DubError(str(exc)) from None
            except ai33_audio.AudioError as exc:
                raise DubError(str(exc), exc.status) from None
            finally:
                upload.unlink(missing_ok=True)
            self.save(job)
        waited = time.monotonic()
        while True:
            if cancel.is_set():
                raise Cancelled()
            time.sleep(4)
            detail = self.poll(g, keys, job)
            if detail is None:
                continue
            if detail['status'] == 'error':
                raise DubError('ai33.pro báo lỗi khi lồng tiếng. Kiểm tra credit, giọng đọc và lịch sử tác vụ ai33.pro.')
            self.progress(job, 'tts', max(.05, detail.get('progress', 0) / 100), f'ai33.pro đang lồng tiếng theo timestamp ({detail.get("progress", 0)}%)…')
            if detail['status'] == 'done' and (detail.get('replacement_audio_url') or detail['audio_url']):
                break
            if time.monotonic() - waited > 3600:
                raise DubError('ai33.pro chưa lồng tiếng xong sau 60 phút. Bấm Tiếp tục để kiểm tra lại (không tạo trùng).')
        url = detail.get('replacement_audio_url')
        job['warnings'] = [w for w in job['warnings'] if not w.startswith('ai33')]
        if not url:
            # only the default dubbed track came back (it keeps the original background): do not add ours on top
            url = detail['audio_url']
            (folder / 'background.wav').unlink(missing_ok=True)
            job['warnings'].append('ai33 không tạo được giọng thay thế' + (f' ({detail["replacement_status"]})' if detail.get('replacement_status') else '')
                                   + '; dùng bản lồng tiếng mặc định của ai33 (giọng ai33 tự chọn, đã kèm nền gốc).')
        download = folder / 'g0.download'
        audio_files.download(url, download)
        g['file'] = 'g0.wav'
        run(['ffmpeg', '-hide_banner', '-nostdin', '-y', '-i', str(download), '-ac', '1', '-ar', str(self.voice_rate(job, download)), str(folder / g['file'])], cancel)
        download.unlink(missing_ok=True)
        with wave.open(str(folder / g['file'])) as w:
            g['clip_seconds'] = round(w.getnframes() / w.getframerate(), 3)
        # ai33's translated SRT becomes the Vietnamese lines (timestamps kept), shown in the job and exported as .srt
        if detail.get('srt_url'):
            try:
                srt = folder / 'ai33.srt'
                audio_files.download(detail['srt_url'], srt)
                rows = parse_srt(srt.read_text(encoding='utf-8-sig', errors='replace'))
                job['segments'] = [dict(start=r['start'], end=r['end'], zh='', vi=r['zh']) for r in rows]
                (folder / 'vi.srt').write_text(to_srt(job['segments'], 'vi'), encoding='utf-8')
            except (DubError, OSError, ai33_audio.AudioError, ValueError):
                job['warnings'].append('ai33 không trả được file SRT tiếng Việt; video vẫn có giọng lồng tiếng.')
        flagged = [i + 1 for i, s in enumerate(job['segments']) if ai_translate.PRICE.search(s.get('vi', '')) or ai_translate.SPEC.search(s.get('vi', ''))]
        if flagged:
            job['warnings'].append(f'ai33 tự dịch: dòng {", ".join(map(str, flagged[:12]))} có thể còn giá/thông số cụ thể (quy tắc không nhắc giá chỉ áp dụng khi app tự dịch).')
        self.save(job)

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
            run(['ffmpeg', '-hide_banner', '-nostdin', '-y', '-i', str(upload), '-map', '0:a:0', '-vn', '-ac', '1', '-ar', str(self.voice_rate(job, upload)), str(folder / 'g0.wav')])
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
        tempo, stretch = 1.0, 1.0
        need = g['clip_seconds'] / room
        lo, hi = settings['min_tempo'], settings['max_tempo']
        # video speed v plays the source v× faster, so the output is 1/v as long (stretch)
        slow, fast = 1 / settings['video_speed_min'], 1 / settings['video_speed_max']
        if settings['align'] == 'auto':
            # both change a little instead of one a lot (the voice ends ~0.3 s before the video)
            tempo, stretch = balance(g['clip_seconds'], max(.5, job['duration'] - start - .3), lo, hi, fast, slow, settings['end_with_voice'])
        if settings['align'] == 'voice':
            # MP3 follows the video within lo–hi
            tempo = min(max(need, lo), hi)
        if settings['align'] == 'video':
            # video follows the MP3 within its speed range
            want = (g['clip_seconds'] / tempo + .3) / max(.5, job['duration'] - start)
            stretch = max(fast, min(slow, want))
        if abs(stretch - 1) < .01:
            stretch = 1.0
        # whatever still does not fit is cut at the end of the video (with a short fade)
        overflow = max(0.0, g['clip_seconds'] / tempo - (max(.5, job['duration'] - start) * stretch - .05))
        job['video_stretch'] = round(stretch, 4)
        job['output_duration'] = round(job['duration'] * stretch, 3)
        place = round(start * stretch, 3)
        voice_end = place + g['clip_seconds'] / tempo - overflow
        if settings['end_with_voice'] and voice_end + .5 < job['output_duration']:
            # still longer than the voice after the speed limits: the video ends shortly after the last word
            job['output_duration'] = round(voice_end + .4, 3)
        g.update(tempo=round(tempo, 4), overflow=round(overflow, 2), raw=g['file'].replace('.wav', '.pcm'), place=place)
        job['warnings'] = [w for w in job['warnings'] if not w.startswith(('Giọng dài', 'Video được', 'Video dài'))]
        if overflow > .05:
            job['warnings'].append(f'Giọng dài hơn video {overflow:.1f}s dù đã khớp trong giới hạn (giọng {tempo:.2f}×, video {1 / stretch:.2f}×); phần cuối giọng được cắt theo độ dài video. Rút gọn đoạn văn hoặc nới giới hạn tốc độ.')
        if job['output_duration'] < round(job['duration'] * stretch, 3) - .05:
            job['warnings'].append(f'Video dài hơn giọng đọc nên được cắt theo giọng: còn {job["output_duration"]:.1f}s.')
        if stretch != 1:
            job['warnings'].append(f'Video được {"làm chậm" if stretch > 1 else "tua nhanh"} cho khớp giọng đọc: dài {job["output_duration"]:.1f}s (gốc {job["duration"]:.1f}s).')
        length = g['clip_seconds'] / tempo - overflow
        fade = f",afade=t=out:st={max(0, length - .3):.3f}:d=0.3,atrim=duration={length:.3f}" if overflow > .05 else ''
        rate = job.get('voice_rate', VOICE_RATE)
        run(['ffmpeg', '-hide_banner', '-nostdin', '-y', '-i', str(folder / g['file']), '-af', tempo_filter(tempo) + fade,
             '-ac', '1', '-ar', str(rate), '-f', 's16le', str(folder / g['raw'])], cancel)
        mix_voice(job['groups'], folder, job['output_duration'], rate)
        # subtitles follow the voice: sentences are spread by length, then each change snaps to the nearest pause in the audio
        pauses = [t / tempo for t in silences(folder / g['file'])]
        job['vi_lines'] = [l for l in sentence_lines(job.get('paragraph') or '', place, length, pauses) if l['start'] < job['output_duration']]

    def export(self, job, folder, source, info, cancel):
        settings = job['options']
        self.progress(job, 'export', .1, 'Đang xuất video MP4…')
        self.save(job)
        timed = settings['mode'] in ('paragraph', 'design')
        stretch = job.get('video_stretch', 1) if timed else 1
        duration = job.get('output_duration', job['duration']) if timed else job['duration']
        subtitle_rows = job.get('vi_lines') if timed else job['segments']
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
        image = self.image(settings['image_id']) if settings['image'] else None
        if settings['image'] and not image:
            job['warnings'] = [w for w in job['warnings'] if not w.startswith('Lớp ảnh')] + ['Lớp ảnh đang bật nhưng chưa chọn ảnh nên video xuất không có lớp ảnh.']
        design = self.design_for(job, folder) if settings.get('design') else None
        adjust = adjust_filters(settings)
        copy = stretch == 1 and identity and not chosen and not image and not design and not adjust and video.get('codec_name') == 'h264' and video.get('pix_fmt') in ('yuv420p', 'yuvj420p')
        filters = not copy
        if filters:
            width, height = frame_size(settings, video)
            # frame → random overlays
            if design:
                lines = design_video(design, width, height, stretch, duration, adjust)
            else:
                lines, _ = frame_graph(settings, video, ([f'setpts=PTS*{stretch:.6f}'] if stretch != 1 else []) + adjust, [])
                lines[-1] = lines[-1][:-len('[vout]')] + '[framed]'
            graph.extend(lines)
            base, index = 'framed', 2 + has_bg + (subs == 'soft')
            scale = width / design_mod.W
            if design:
                # nền + vùng hòa nền drawn over the video (the editor's look), below overlays and the frame
                bg_png, frame_png = design_mod.artwork_layers(design)
                (folder / 'design-bg.png').write_bytes(bg_png)
                (folder / 'design-frame.png').write_bytes(frame_png)
                args += ['-loop', '1', '-framerate', '30', '-t', f'{duration:.3f}', '-i', 'design-bg.png']
                graph.append(f'[{index}:v]scale={width}:{height}:flags=lanczos,format=rgba[dbg]')
                graph.append(f'[{base}][dbg]overlay=0:0:format=auto:shortest=1[designbg]')
                base, index = 'designbg', index + 1
            def add_image(base, index):
                nonlocal args
                args += ['-loop', '1', '-framerate', '30', '-t', f'{duration:.3f}', '-i', str(self.image_dir / image['file'])]
                more, base = image_chain(index, settings, width, height, base, duration)
                graph.extend(more)
                return base, index + 1
            if image and settings['image_layer'] == 'below':
                base, index = add_image(base, index)
            for k, item in enumerate(chosen):
                if settings['overlay_timing'] == 'sequence' and item.get('sequence'):
                    # joined clips: each normalised to the frame, concatenated, then cut to the video's length
                    parts = []
                    for n, clip in enumerate(item['sequence']):
                        meta = self.overlay(clip)
                        if not meta:
                            continue
                        args += (['-loop', '1', '-t', '3'] if meta['still'] else []) + overlay_decoder(meta) + ['-i', str(self.overlay_dir / meta['file'])]
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
                        args += (['-stream_loop', '-1'] if settings['overlay_timing'] == 'loop' else []) + overlay_decoder(meta) + ['-i', path]
                    source = f'[{index}:v]'
                    index += 1
                clips = [self.overlay(c) for c in item.get('sequence') or [item['id']]] if settings['overlay_timing'] == 'sequence' else [self.overlay(item['id'])]
                alpha = all(c and c.get('alpha') for c in clips)
                more, base = overlay_chain(source, dict(item, k=k, alpha=alpha), width, height, settings, base, duration)
                graph.extend(more)
            if image and settings['image_layer'] == 'above':
                base, index = add_image(base, index)
            text = 'null'
            if design:
                # khung → khung PNG riêng → ảnh/logo → nền chữ → tiêu đề, nội dung (shared with the editor)
                args += ['-loop', '1', '-framerate', '30', '-t', f'{duration:.3f}', '-i', 'design-frame.png']
                graph.append(f'[{index}:v]scale={width}:{height}:flags=lanczos,format=rgba[dfr]')
                graph.append(f'[{base}][dfr]overlay=0:0:format=auto:shortest=1[designfr]')
                base, index = 'designfr', index + 1
                frame_file = self.frames_dir / (design['frame_id'] + '.png') if design['frame_style'] == 'custom' and self.frames_dir else None
                try:
                    base, index, text = design_layers(folder, design, args, graph, base, index, scale, duration, frame_file, self.images_dir, font_dir='')
                except ValueError as exc:
                    raise DubError('Thiết kế: ' + str(exc)) from None
            graph.append(f'[{base}]' + ('' if text == 'null' else text + ',') + 'format=yuv420p[vout]')
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
                saved = output_folder.deliver(self.settings_path, folder / 'dubbed.mp4', job.get('file_name') or job['name'] + ('-dung' if settings['mode'] == 'design' else '-long-tieng'))
                job['outputs']['saved_path'] = str(saved)
                if subs in ('file', 'soft'):
                    shutil.copyfile(folder / 'vi.srt', saved.with_suffix('.srt'))
        except (ValueError, OSError) as exc:
            job['warnings'].append(str(exc))

    # ---- image layer (one picture placed on every dubbed video: a cover box, frame, logo, sticker…)
    @property
    def image_dir(self):
        folder = self.root.parent / 'dub-images'
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def images(self):
        rows = []
        for meta in self.image_dir.glob('*.json'):
            try:
                item = json.loads(meta.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            if isinstance(item, dict) and item.get('id') == meta.stem and (self.image_dir / item.get('file', '')).is_file():
                rows.append(item)
        return sorted(rows, key=lambda r: r.get('created', ''), reverse=True)

    def image(self, key):
        if not isinstance(key, str) or not re.fullmatch('[a-f0-9]{32}', key):
            return None
        return next((o for o in self.images() if o['id'] == key), None)

    def import_image(self, upload, name):
        ext = Path(str(name)).suffix.lower()
        if ext not in IMAGE_TYPES:
            raise DubError('Lớp ảnh cần là PNG, JPG hoặc WebP.')
        key = uuid.uuid4().hex
        target = self.image_dir / (key + ext)
        shutil.move(str(upload), target)
        info = probe(target)
        if not info['video'] or not info['video'].get('width'):
            target.unlink(missing_ok=True)
            raise DubError('Không đọc được ảnh.')
        item = dict(id=key, name=re.sub(r'[\x00-\x1f<>:"/\\|?*]', '_', Path(str(name)).name)[:120], file=target.name,
                    width=int(info['video']['width']), height=int(info['video']['height']), alpha=overlay_alpha(target)[0],
                    created=time.strftime('%Y-%m-%dT%H:%M:%S'))
        (self.image_dir / (key + '.json')).write_text(json.dumps(item, ensure_ascii=False), encoding='utf-8')
        return item

    def delete_image(self, key):
        item = self.image(key)
        if not item:
            raise DubError('Không tìm thấy ảnh.', 404)
        for path in (self.image_dir / item['file'], self.image_dir / (key + '.json')):
            path.unlink(missing_ok=True)

    # ---- overlay library (videos/GIF/PNG put on top of dubbed videos, picked at random per video)
    def overlays(self):
        rows = []
        for meta in self.overlay_dir.glob('*.json'):
            try:
                item = json.loads(meta.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            if isinstance(item, dict) and item.get('id') == meta.stem and (self.overlay_dir / item.get('file', '')).is_file():
                if 'alpha' not in item:  # imported before 0.17.6
                    item['alpha'], item['codec'] = overlay_alpha(self.overlay_dir / item['file'])
                    try:
                        meta.write_text(json.dumps(item, ensure_ascii=False), encoding='utf-8')
                    except OSError:
                        pass
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
        alpha, codec = overlay_alpha(target)
        item = dict(id=key, name=re.sub(r'[\x00-\x1f<>:"/\\|?*]', '_', Path(str(name)).name)[:120], file=target.name, still=still, alpha=alpha, codec=codec,
                    duration=0 if still else round(info['duration'], 2), width=int(info['video'].get('width') or 0), height=int(info['video'].get('height') or 0),
                    created=time.strftime('%Y-%m-%dT%H:%M:%S'))
        item['size'] = target.stat().st_size
        (self.overlay_dir / (key + '.json')).write_text(json.dumps(item, ensure_ascii=False), encoding='utf-8')
        # the browser preview copy is made on first view, so importing a folder of big MOV files stays fast
        return item

    def overlay_thumb(self, item):
        """Small picture for the library list. Transparent overlays get a PNG that keeps the alpha (shown on a
        checkerboard); a JPG would turn the transparent area black and every live-comment overlay would look empty."""
        jpg = self.overlay_dir / (item['id'] + '.jpg')
        if not item.get('alpha'):
            return jpg if jpg.is_file() else None
        png = self.overlay_dir / (item['id'] + '.png')
        if not png.is_file():
            at = '0' if item['still'] else f"{min(3.0, max(0.0, (item.get('duration') or 0) / 3)):.2f}"
            try:
                run(['ffmpeg', '-hide_banner', '-nostdin', '-y', '-ss', at, *overlay_decoder(item), '-i', str(self.overlay_dir / item['file']),
                     '-frames:v', '1', '-vf', 'scale=240:-2,format=rgba', str(png)], timeout=60)
            except DubError:
                return jpg if jpg.is_file() else None
        return png

    def overlay_preview(self, item):
        """File the browser can show: the original when Chrome plays it, else a WebM VP9 copy that keeps the
        transparency (ProRes/QuickTime MOV with alpha cannot play in a browser). Made once, then reused."""
        if item['still'] or (not item.get('alpha') and item.get('codec') in BROWSER_VIDEO and Path(item['file']).suffix.lower() in ('.mp4', '.m4v', '.webm')):
            return self.overlay_dir / item['file']
        target = self.overlay_dir / (item['id'] + '.preview.webm')
        with self.__dict__.setdefault('_preview_locks', {}).setdefault(item['id'], threading.Lock()):
            return self._overlay_preview(item, target)

    def _overlay_preview(self, item, target):
        if not target.is_file():
            temp = target.with_suffix('.part.webm')
            try:
                run(['ffmpeg', '-hide_banner', '-nostdin', '-y', *overlay_decoder(item), '-i', str(self.overlay_dir / item['file']), '-t', '120', '-an',
                     '-vf', "fps=30,scale=-2:'min(720,ih)'", '-c:v', 'libvpx-vp9', '-pix_fmt', 'yuva420p' if item.get('alpha') else 'yuv420p',
                     '-b:v', '0', '-crf', '36', '-deadline', 'realtime', '-cpu-used', '8', '-row-mt', '1', str(temp)], timeout=600)
                temp.replace(target)
            except DubError:
                temp.unlink(missing_ok=True)
                return self.overlay_dir / item['file']
        return target

    def delete_overlay(self, key):
        item = self.overlay(key)
        if not item:
            raise DubError('Không tìm thấy overlay.', 404)
        for path in (self.overlay_dir / item['file'], self.overlay_dir / (key + '.json'), self.overlay_dir / (key + '.jpg'), self.overlay_dir / (key + '.png'), self.overlay_dir / (key + '.preview.webm')):
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
               (['-c:v', 'copy'] if job.get('video_stretch', 1) == 1 or job['options']['mode'] not in ('paragraph', 'design') else
                ['-filter:v', f'setpts=PTS*{job["video_stretch"]:.6f}', *self.encoder_args('cpu', 'high')] +
                (['-filter:a', tempo_filter(1 / job['video_stretch'])] if background.is_file() else [])) + \
               ['-t', str(job.get('output_duration', job['duration'])), '-f', 'mp4', str(target)]
        run(args)
        asset = import_audio(folder / 'voice.wav', job['name'] + ' · giọng Việt')
        return dict(audio_asset_id=asset['asset_id'])
