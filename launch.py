"""Portable launcher: checks prerequisites, then opens the local application."""
import os
import socket
import shutil
import subprocess
import sys
import threading
import json
import time
import webbrowser
from urllib import request
from pathlib import Path

ROOT = Path(__file__).resolve().parent


HIDDEN = '--hidden' in sys.argv   # started without a console window: errors go to a dialog


def already_running(port):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=.5):
            return True
    except OSError:
        return False


def version():
    try:
        return (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
    except OSError:
        return ''


def same_app(port):
    """True when the app on this port is this folder at this version (0.19.0 and older have no /app/info)."""
    try:
        with request.urlopen(f'http://127.0.0.1:{port}/app/info', timeout=3) as response:
            info = json.loads(response.read(4096))
        return info.get('version') == version() and os.path.normcase(info.get('root', '')) == os.path.normcase(str(ROOT))
    except (OSError, ValueError):
        return False


def stop_other(port):
    try:
        req = request.Request(f'http://127.0.0.1:{port}/app/quit', data=b'{}', method='POST',
                              headers={'Content-Type': 'application/json', 'Origin': f'http://127.0.0.1:{port}'})
        request.urlopen(req, timeout=5).read()
    except OSError:
        pass
    for _ in range(40):
        if not already_running(port):
            time.sleep(.5)
            return
        time.sleep(.25)
    raise RuntimeError(f'Cong {port} dang bi mot ung dung khac dung. Tat Review Studio cu (nut nguon) hoac khoi dong lai may roi mo lai.')


def tell(message):
    """Startup error: a Windows message box when there is no console, otherwise the terminal."""
    log = ROOT / '.local' / 'launch.log'
    try:
        log.parent.mkdir(exist_ok=True)
        log.write_text(message + '\n', encoding='utf-8')
    except OSError:
        pass
    if HIDDEN and os.name == 'nt':
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message + '\n\nMở START_WINDOWS.bat để xem chi tiết.', 'Review Studio', 0x10)
    else:
        print(f'Khong khoi dong duoc: {message}', file=sys.stderr)


def main():
    if sys.version_info < (3, 11):
        raise RuntimeError('Can Python 3.11 tro len. Xem HUONG_DAN.txt.')
    os.environ['PATH'] = str(ROOT / 'bin') + os.pathsep + os.environ.get('PATH', '')
    # FFmpeg missing or too limited: on Windows it is downloaded once into bin/ (no searching, no setup)
    import ffmpeg_setup
    if ffmpeg_setup.usable() and HIDDEN and os.name == 'nt':
        # no console to show the progress: say what is happening (the app opens by itself when it is done)
        import ctypes
        threading.Thread(target=lambda: ctypes.windll.user32.MessageBoxW(
            None, 'Lan dau chay: dang tai FFmpeg (khoang 200 MB, vai phut).\nUng dung se tu mo khi tai xong.\n\n'
                  'Muon xem tien do: mo START_WINDOWS.bat thay cho loi tat.', 'Review Studio', 0x40), daemon=True).start()
    if ffmpeg_setup.usable() and not ffmpeg_setup.install(ROOT, lambda text: print(text, flush=True)):
        raise RuntimeError('Chua co FFmpeg (' + ffmpeg_setup.usable() + '). Kiem tra mang roi mo lai, hoac cai theo HUONG_DAN.txt.')
    for font in ('DejaVuSans.ttf', 'DejaVuSans-Bold.ttf', 'DejaVuSerif.ttf',
                 'DejaVuSerif-Bold.ttf', 'DejaVuSansMono.ttf', 'DejaVuSansMono-Bold.ttf'):
        if not (ROOT / 'assets' / font).is_file():
            raise RuntimeError('Thieu phong chu. Hay giai nen toan bo ZIP vao mot thu muc.')
    port = int(os.environ.get('PORT', '8000'))
    if already_running(port):
        if same_app(port):
            # opened twice (e.g. the desktop shortcut): just bring the browser to the running app
            webbrowser.open(f'http://127.0.0.1:{port}')
            return 0
        # another version or another folder is still running (e.g. an old window left open): stop it
        print('Dang tat ban Review Studio cu dang chay...', flush=True)
        stop_other(port)
    print(f'Mo trinh duyet: http://127.0.0.1:{port}', flush=True)
    print('Giu cua so nay mo khi dung. Nhan Ctrl+C de dung.', flush=True)
    if '--no-browser' not in sys.argv:
        timer = threading.Timer(1.5, lambda: webbrowser.open(f'http://127.0.0.1:{port}'))
        timer.daemon = True
        timer.start()
    # The app runs as a child process so "Khởi động lại" after an in-app update (exit code 75) brings it back.
    env = {**os.environ, 'REVIEW_LAUNCHER': '1'}
    while True:
        code = subprocess.call([sys.executable, str(ROOT / 'app.py')], cwd=ROOT, env=env)
        if code != 75:
            return code
        print('Dang khoi dong lai Review Studio sau khi cap nhat...', flush=True)


if __name__ == '__main__':
    try:
        sys.exit(main() or 0)
    except KeyboardInterrupt:
        pass
    except Exception as error:
        tell(str(error))
        sys.exit(1)
