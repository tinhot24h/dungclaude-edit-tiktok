"""FFmpeg for the app, installed by itself on Windows: when ffmpeg/ffprobe are missing (or lack drawtext/libx264),
a ready-made Windows build is downloaded once and ffmpeg.exe + ffprobe.exe are put in bin/ next to launch.py
(launch.py puts bin/ first on PATH). Nothing is installed system-wide; deleting bin/ undoes it."""
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from urllib import request

# full builds: libx264, drawtext, libass ("Phụ đề chữ chạy"), NVENC. The first that downloads is used.
SOURCES = (
    'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip',
    'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip',
)
TOOLS = ('ffmpeg', 'ffprobe')


def usable():
    """'' when ffmpeg and ffprobe on PATH can run the app, else why not."""
    for tool in TOOLS:
        if not shutil.which(tool):
            return f'chưa có {tool}'
    try:
        filters = subprocess.run(['ffmpeg', '-hide_banner', '-filters'], capture_output=True, text=True, timeout=30).stdout
        encoders = subprocess.run(['ffmpeg', '-hide_banner', '-encoders'], capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return 'ffmpeg không chạy được'
    if 'drawtext' not in filters or 'libx264' not in encoders:
        return 'bản ffmpeg thiếu drawtext/libx264'
    return ''


def download(url, target, say):
    req = request.Request(url, headers={'User-Agent': 'ReviewStudio'})
    with request.urlopen(req, timeout=60) as response, open(target, 'wb') as out:
        total, done, shown, start = int(response.headers.get('Content-Length') or 0), 0, -1, time.time()
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if total:
                pct = done * 100 // total
                if pct // 5 != shown:
                    shown = pct // 5
                    speed = done / max(.1, time.time() - start) / 1048576
                    say(f'  Dang tai FFmpeg: {pct}% ({done // 1048576}/{total // 1048576} MB, {speed:.1f} MB/s)')
    if total and done < total:
        raise OSError('tai chua het file')


def install(root, say=print, windows=None):
    """Download and unpack ffmpeg.exe + ffprobe.exe into root/bin. Returns True when they run afterwards."""
    if not (os.name == 'nt' if windows is None else windows):
        say('Tu cai FFmpeg chi ho tro Windows. Tren macOS: brew install ffmpeg · Linux: sudo apt install ffmpeg')
        return False
    bin_dir = Path(root) / 'bin'
    bin_dir.mkdir(exist_ok=True)
    archive = bin_dir / 'ffmpeg-download.zip'
    say('Chua co FFmpeg: dang tu tai ban cho Windows (khoang 100-200 MB, chi tai 1 lan)...')
    for url in SOURCES:
        try:
            say('  Nguon: ' + url.split('/')[2])
            download(url, archive, say)
            with zipfile.ZipFile(archive) as z:
                names = {Path(n).stem.lower(): n for n in z.namelist() if n.lower().endswith('/bin/ffmpeg.exe') or n.lower().endswith('/bin/ffprobe.exe')}
                if set(names) != set(TOOLS):
                    raise OSError('file tai ve khong co ffmpeg.exe/ffprobe.exe')
                for tool, name in names.items():
                    part = bin_dir / (tool + '.exe.part')
                    with z.open(name) as src, open(part, 'wb') as dst:
                        shutil.copyfileobj(src, dst, 1024 * 1024)
                    part.replace(bin_dir / (tool + '.exe'))
            archive.unlink(missing_ok=True)
            os.environ['PATH'] = str(bin_dir) + os.pathsep + os.environ.get('PATH', '')
            problem = usable()
            if not problem:
                say('Da cai FFmpeg vao thu muc bin cua ung dung.')
                return True
            say('  Ban vua tai chua dung duoc: ' + problem)
        except (OSError, zipfile.BadZipFile) as exc:
            say(f'  Khong tai duoc tu nguon nay ({exc}). Thu nguon khac...')
        archive.unlink(missing_ok=True)
    say('Khong tu cai duoc FFmpeg. Kiem tra mang, hoac cai tay theo HUONG_DAN.txt (winget install --exact --id Gyan.FFmpeg).')
    return False


if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    os.environ['PATH'] = str(root / 'bin') + os.pathsep + os.environ.get('PATH', '')
    sys.exit(0 if not usable() or install(root) else 1)
