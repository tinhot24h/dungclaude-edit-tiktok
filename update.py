"""Update Review Studio in place from GitHub: only changed files are downloaded, each one is checked against
the SHA-256 in the published MANIFEST.json, the old files are backed up, then swapped in. User data in .local/
(videos, MP3, projects, settings) is never touched.

    python update.py           check and install the newest version
    python update.py --check   only report what would change
"""
import hashlib
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from urllib import request, error

ROOT = Path(__file__).resolve().parent
REPO = os.environ.get('REVIEW_UPDATE_REPO', 'tinhot24h/dungclaude-edit-tiktok')
BRANCH = os.environ.get('REVIEW_UPDATE_BRANCH', 'main')
SOURCE = os.environ.get('REVIEW_UPDATE_URL', '').rstrip('/') + '/' if os.environ.get('REVIEW_UPDATE_URL') else ''
_pinned = {}
WORK = ROOT / '.local' / 'update'
SAFE = re.compile(r'[A-Za-z0-9_.][A-Za-z0-9_.\-]*')
FILE_LIMIT = 50 * 1024 * 1024


class UpdateError(Exception):
    pass


def version_key(value):
    try:
        return tuple(int(part) for part in str(value).strip().split('.'))
    except ValueError:
        return (0,)


def safe_path(name):
    """Relative POSIX path inside the app folder; never .local/.git, absolute paths or '..'."""
    if not isinstance(name, str) or not 0 < len(name) <= 200 or '\\' in name:
        raise UpdateError('Danh sách cập nhật có đường dẫn không hợp lệ.')
    parts = name.split('/')
    if not parts or any(not SAFE.fullmatch(p) or p in ('.', '..') for p in parts) or parts[0] in ('.local', '.git'):
        raise UpdateError('Danh sách cập nhật có đường dẫn không hợp lệ: ' + name)
    return ROOT.joinpath(*parts)


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def source():
    """Download base pinned to the newest commit of the branch. raw.githubusercontent.com caches each file on its
    own for a few minutes after a push, so by branch name the MANIFEST and the files could come from different
    versions; by commit they always match. Falls back to the branch when the GitHub API is unreachable."""
    if SOURCE:
        return SOURCE
    if 'base' not in _pinned:
        base = f'https://raw.githubusercontent.com/{REPO}/{BRANCH}/'
        try:
            req = request.Request(f'https://api.github.com/repos/{REPO}/commits/{BRANCH}',
                                  headers={'User-Agent': 'ReviewStudio-updater', 'Accept': 'application/vnd.github.sha'})
            with request.urlopen(req, timeout=20) as response:
                sha = response.read(100).decode('ascii', 'replace').strip()
            if re.fullmatch(r'[0-9a-f]{40}', sha):
                base = f'https://raw.githubusercontent.com/{REPO}/{sha}/'
        except (error.URLError, TimeoutError, OSError, ValueError):
            pass
        _pinned['base'] = base
    return _pinned['base']


def fetch(name, limit=FILE_LIMIT):
    url = source() + name + '?t=' + str(int(time.time()))
    try:
        with request.urlopen(request.Request(url, headers={'User-Agent': 'ReviewStudio-updater', 'Cache-Control': 'no-cache'}), timeout=60) as response:
            data = response.read(limit + 1)
    except error.HTTPError as exc:
        raise UpdateError(f'GitHub trả lỗi HTTP {exc.code} khi tải {name}. Thử lại sau.') from None
    except (error.URLError, TimeoutError, OSError):
        raise UpdateError('Không kết nối được GitHub. Kiểm tra mạng/proxy rồi thử lại.') from None
    if len(data) > limit:
        raise UpdateError(f'{name} lớn bất thường; dừng cập nhật.')
    return data


def manifest(data):
    try:
        value = json.loads(data)
    except ValueError:
        raise UpdateError('MANIFEST.json trên GitHub không hợp lệ.') from None
    files = value.get('files') if isinstance(value, dict) else None
    if not isinstance(files, dict) or not isinstance(value.get('version'), str) or not files:
        raise UpdateError('MANIFEST.json trên GitHub không hợp lệ.')
    for name, info in files.items():
        safe_path(name)
        if not isinstance(info, dict) or not re.fullmatch('[0-9a-f]{64}', str(info.get('sha256', ''))) or not isinstance(info.get('size'), int):
            raise UpdateError('MANIFEST.json trên GitHub không hợp lệ.')
    return value


def local_manifest():
    try:
        return json.loads((ROOT / 'MANIFEST.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def local_version():
    try:
        return (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
    except OSError:
        return '0'


def check():
    """What an update would do: remote version, files to download and files to remove."""
    remote = manifest(fetch('MANIFEST.json', 1024 * 1024))
    changed = []
    for name, info in sorted(remote['files'].items()):
        path = safe_path(name)
        if name == 'MANIFEST.json':
            continue
        if not path.is_file() or path.stat().st_size != info['size'] or digest(path) != info['sha256']:
            changed.append(name)
    old = local_manifest().get('files', {})
    removed = sorted(n for n in old if n not in remote['files'] and n != 'MANIFEST.json' and safe_path(n).is_file())
    current = local_version()
    return dict(current=current, latest=remote['version'], newer=version_key(remote['version']) > version_key(current),
                changed=changed, removed=removed, bytes=sum(remote['files'][n]['size'] for n in changed),
                notes=remote.get('notes', '') if isinstance(remote.get('notes', ''), str) else '', manifest=remote)


def apply(plan=None, log=print):
    plan = plan or check()
    if not plan['changed'] and not plan['removed']:
        return dict(updated=False, version=plan['current'], files=0)
    staging = WORK / 'staging'
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    files = plan['manifest']['files']
    for i, name in enumerate(plan['changed'], 1):
        log(f'[{i}/{len(plan["changed"])}] Tải {name}')
        try:
            data = fetch(name, files[name]['size'] + 16)
        except UpdateError as exc:
            if 'lớn bất thường' not in str(exc):
                raise
            data = b''
        if len(data) != files[name]['size'] or hashlib.sha256(data).hexdigest() != files[name]['sha256']:
            raise UpdateError(f'{name} tải về không khớp mã kiểm tra (có thể GitHub đang cập nhật). Chạy lại sau 1 phút.')
        target = staging / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    # Everything verified: back up what is replaced/removed, then swap files in.
    backup = WORK / ('backup-' + re.sub(r'[^0-9.]', '_', plan['current']) + '-' + time.strftime('%Y%m%d-%H%M%S'))
    for name in plan['changed'] + plan['removed'] + ['MANIFEST.json']:
        path = safe_path(name)
        if path.is_file():
            (backup / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup / name)
    for name in plan['changed']:
        path = safe_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging / name, path)
    for name in plan['removed']:
        safe_path(name).unlink(missing_ok=True)
    (ROOT / 'MANIFEST.json').write_text(json.dumps(plan['manifest'], ensure_ascii=False, indent=1), encoding='utf-8')
    shutil.rmtree(staging, ignore_errors=True)
    for old in sorted(WORK.glob('backup-*'))[:-3]:
        shutil.rmtree(old, ignore_errors=True)
    return dict(updated=True, version=plan['latest'], files=len(plan['changed']), removed=len(plan['removed']), backup=str(backup))


def main():
    if (ROOT / '.git').exists():
        print('Thư mục này là bản git clone: cập nhật bằng lệnh  git pull')
        return 0
    print(f'Review Studio {local_version()} · kiểm tra bản mới trên GitHub ({REPO})…')
    try:
        plan = check()
        if not plan['changed'] and not plan['removed']:
            print(f'Đang dùng bản mới nhất ({plan["current"]}).')
            return 0
        print(f'Bản trên GitHub: {plan["latest"]} · {len(plan["changed"])} file cần tải ({plan["bytes"] // 1024} KB)'
              + (f', {len(plan["removed"])} file cũ sẽ xóa' if plan['removed'] else '') + '.')
        if '--check' in sys.argv:
            for name in plan['changed']:
                print('  ~ ' + name)
            for name in plan['removed']:
                print('  - ' + name)
            return 0
        result = apply(plan)
        print(f'Đã cập nhật lên {result["version"]}. Bản cũ được sao lưu ở {result["backup"]}.')
        print('Mở lại ứng dụng (START_WINDOWS.bat) để dùng bản mới.')
        return 0
    except UpdateError as exc:
        print('Không cập nhật được: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
