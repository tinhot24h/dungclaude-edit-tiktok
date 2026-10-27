"""Portable launcher: checks prerequisites, then opens the local application."""
import os
import runpy
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    if sys.version_info < (3, 11):
        raise RuntimeError('Can Python 3.11 tro len. Xem HUONG_DAN.txt.')
    os.environ['PATH'] = str(ROOT / 'bin') + os.pathsep + os.environ.get('PATH', '')
    for tool in ('ffmpeg', 'ffprobe'):
        if not shutil.which(tool):
            raise RuntimeError(f'Chua co {tool}. Cai FFmpeg theo HUONG_DAN.txt roi mo lai.')
        subprocess.run([tool, '-version'], check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.PIPE, timeout=20)
    filters = subprocess.run(['ffmpeg', '-hide_banner', '-filters'],
                             capture_output=True, text=True, check=True, timeout=20)
    encoders = subprocess.run(['ffmpeg', '-hide_banner', '-encoders'],
                              capture_output=True, text=True, check=True, timeout=20)
    if 'drawtext' not in filters.stdout or 'libx264' not in encoders.stdout:
        raise RuntimeError('Ban FFmpeg can co drawtext va libx264. Xem HUONG_DAN.txt.')
    for font in ('DejaVuSans.ttf', 'DejaVuSans-Bold.ttf', 'DejaVuSerif.ttf',
                 'DejaVuSerif-Bold.ttf', 'DejaVuSansMono.ttf', 'DejaVuSansMono-Bold.ttf'):
        if not (ROOT / 'assets' / font).is_file():
            raise RuntimeError('Thieu phong chu. Hay giai nen toan bo ZIP vao mot thu muc.')
    port = int(os.environ.get('PORT', '8000'))
    print(f'Mo trinh duyet: http://127.0.0.1:{port}', flush=True)
    print('Giu cua so nay mo khi dung. Nhan Ctrl+C de dung.', flush=True)
    if '--no-browser' not in sys.argv:
        timer = threading.Timer(1.5, lambda: webbrowser.open(f'http://127.0.0.1:{port}'))
        timer.daemon = True
        timer.start()
    runpy.run_path(str(ROOT / 'app.py'), run_name='__main__')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as error:
        print(f'Khong khoi dong duoc: {error}', file=sys.stderr)
        sys.exit(1)
