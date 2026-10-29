"""🩺 Kiểm tra hệ thống: everything the app needs on this computer, each with what is wrong and how to fix it.
Read-only (installs nothing): Python, FFmpeg and the features the export uses, hardware encoders, Demucs, the API
keys (one free request each), the output folder, free disk space, fonts and the Windows metadata writer."""
import os
import re
import shutil
import subprocess
import sys
from urllib import error, request

import ai33_audio
import dubbing
import fonts
import media_engine
import output_folder
import secrets_store

OK, WARN, BAD, INFO = 'ok', 'warn', 'bad', 'info'
GB = 1024 ** 3


def row(key, label, state, detail, fix=''):
    return dict(key=key, label=label, state=state, detail=detail, fix=fix)


def ffmpeg_lists():
    try:
        run = lambda *a: subprocess.run(['ffmpeg', '-hide_banner', *a], capture_output=True, text=True, timeout=30).stdout
        return run('-version').splitlines()[0] if run('-version') else '', run('-filters'), run('-encoders')
    except (OSError, subprocess.SubprocessError):
        return '', '', ''


def has_filter(listing, name):
    return bool(re.search(r'^\s*\S+\s+' + re.escape(name) + r'\s', listing, re.M))


def free_space(path):
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return None


def openai_ok(key):
    """A free request (the model list) proves the key and the connection."""
    req = request.Request(dubbing.OPENAI + 'models', headers={'Authorization': 'Bearer ' + key})
    try:
        with request.urlopen(req, timeout=12):
            return ''
    except error.HTTPError as exc:
        return 'key không hợp lệ hoặc hết hiệu lực' if exc.code in (401, 403) else f'OpenAI trả lỗi HTTP {exc.code}'
    except (error.URLError, OSError):
        return 'không kết nối được api.openai.com'


def run(root, data_dir, settings_path, network=True):
    rows = []
    v = sys.version_info
    rows.append(row('python', 'Python', OK if v >= (3, 11) else BAD, f'{v.major}.{v.minor}.{v.micro} · {sys.executable}',
                    '' if v >= (3, 11) else 'Cần Python 3.11 trở lên: chạy START_WINDOWS.bat để tự cài Python 3.12.'))

    where = shutil.which('ffmpeg')
    version, filters, encoders = ffmpeg_lists() if where else ('', '', '')
    local = bool(where) and os.path.normcase(os.path.dirname(where)) == os.path.normcase(str(root / 'bin'))
    if not where or not shutil.which('ffprobe'):
        rows.append(row('ffmpeg', 'FFmpeg / FFprobe', BAD, 'chưa có ' + ('ffprobe' if where else 'ffmpeg'),
                        'Đóng app rồi mở lại bằng START_WINDOWS.bat: app tự tải FFmpeg vào thư mục bin.'))
    else:
        rows.append(row('ffmpeg', 'FFmpeg / FFprobe', OK, (version.replace('ffmpeg version ', '').split(' Copyright')[0][:60] or 'có') + (' · trong thư mục bin của app' if local else ' · cài trên máy')))
        need = [('drawtext', 'chữ trên video (tiêu đề, nội dung)', filters, True), ('libx264', 'xuất MP4 H.264', encoders, False),
                ('libmp3lame', 'giọng đọc MP3', encoders, False), ('sidechaincompress', 'nhạc nền tự giảm khi có giọng', filters, True),
                ('blend', 'lớp ảnh / overlay hòa trộn', filters, True)]
        missing = [label for name, label, listing, is_filter in need if not (has_filter(listing, name) if is_filter else name in listing)]
        rows.append(row('ffmpeg_features', 'Tính năng FFmpeg', BAD if missing else OK, ('thiếu: ' + ', '.join(missing)) if missing else 'đủ cho xuất video',
                        'Xóa thư mục bin (nếu có) rồi mở lại bằng START_WINDOWS.bat để tải bản FFmpeg đầy đủ.' if missing else ''))
        ass = has_filter(filters, 'ass')
        rows.append(row('libass', 'Phụ đề chữ chạy (libass)', OK if ass else WARN, 'có' if ass else 'bản FFmpeg này thiếu libass: video xuất không có phụ đề chữ chạy',
                        '' if ass else 'Xóa thư mục bin rồi mở lại bằng START_WINDOWS.bat để tải bản FFmpeg đầy đủ (có libass).'))
        hw = media_engine.hardware_encoders()
        rows.append(row('gpu', 'Xuất bằng card đồ họa', OK if hw else INFO, ', '.join(hw) if hw else 'không có (xuất bằng CPU, chậm hơn nhưng vẫn chạy)',
                        '' if hw else 'Máy có card NVIDIA: cập nhật driver mới để dùng NVENC.'))

    demucs = dubbing.demucs_command()
    rows.append(row('demucs', 'Tách giọng AI (Demucs)', OK if demucs else INFO, 'đã cài' if demucs else 'chưa cài · chỉ cần khi chọn "Tách giọng AI"',
                    '' if demucs else 'Bấm "⬇ Cài Demucs tự động" ở mục 🎵 Âm thanh gốc khi cần.'))

    for provider, label in (('openai', 'OpenAI key'), ('ai33', 'ai33.pro key')):
        key = secrets_store.get(provider)
        if not key:
            rows.append(row(provider, label, WARN, 'chưa lưu key', 'Bấm 🔑 API key trên thanh trên cùng để nhập và lưu key.'))
            continue
        if not network:
            rows.append(row(provider, label, OK, 'đã lưu'))
            continue
        if provider == 'openai':
            problem = openai_ok(key)
            rows.append(row(provider, label, BAD if 'key' in problem else WARN if problem else OK, problem or 'hợp lệ, kết nối được',
                            'Kiểm tra key ở 🔑 API key hoặc mạng Internet.' if problem else ''))
        else:
            try:
                left = ai33_audio.credits({})['credits']
                low = isinstance(left, (int, float)) and left < 2000
                rows.append(row(provider, label, WARN if low else OK, f'hợp lệ · còn ◆ {left:,.0f} credit'.replace(',', '.'), 'Credit sắp hết: nạp thêm ở ai33.pro.' if low else ''))
            except ai33_audio.AudioError as exc:
                rows.append(row(provider, label, BAD, str(exc)[:160], 'Kiểm tra key ở 🔑 API key hoặc mạng Internet.'))

    out = output_folder.load(settings_path)
    try:
        folder = output_folder.check_dir(out['output_dir'])
        space = free_space(folder)
        rows.append(row('output', 'Thư mục xuất', OK if space is None or space > 5 * GB else WARN, f'{folder}' + (f' · trống {space / GB:.1f} GB' if space is not None else ''),
                        'Ổ đĩa sắp đầy: dọn bớt hoặc chọn thư mục xuất ở ổ khác.' if space is not None and space <= 5 * GB else ''))
    except ValueError as exc:
        rows.append(row('output', 'Thư mục xuất', BAD, str(exc), 'Chọn lại thư mục xuất ở nút thông số xuất (góc trên bên phải).'))
    space = free_space(data_dir)
    if space is not None:
        state = BAD if space < GB else WARN if space < 5 * GB else OK
        rows.append(row('disk', 'Ổ đĩa của app (.local)', state, f'trống {space / GB:.1f} GB',
                        '' if state == OK else 'Bấm ⋯ → "💾 Dọn file tạm" ở Hàng đợi, hoặc xóa bớt video đã xong.'))

    lost = [f for f, _, _ in fonts.FONTS.values() if not (fonts.ROOT / 'assets' / f).is_file()]
    rows.append(row('fonts', 'Phông chữ', BAD if lost else OK, ('thiếu ' + ', '.join(lost[:4])) if lost else f'đủ {len(fonts.FONTS)} phông',
                    'Giải nén lại toàn bộ file ZIP vào thư mục app.' if lost else ''))

    if os.name == 'nt':
        try:
            ok = subprocess.run([sys.executable, '-c', 'import pythoncom; from win32com.propsys import propsys'], capture_output=True, timeout=30).returncode == 0
        except (OSError, subprocess.SubprocessError):
            ok = False
        rows.append(row('winmeta', 'Ghi thông tin file Windows (pywin32)', OK if ok else INFO, 'có' if ok else 'chưa có · app tự cài khi xuất video có Thông tin file',
                        '' if ok else 'Không cần làm gì: lần xuất đầu tiên app tự cài pywin32.'))

    worst = BAD if any(r['state'] == BAD for r in rows) else WARN if any(r['state'] == WARN for r in rows) else OK
    return dict(state=worst, rows=rows, version=(root / 'VERSION').read_text(encoding='utf-8').strip() if (root / 'VERSION').is_file() else '',
                platform=sys.platform)
