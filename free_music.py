"""Royalty-free music from Openverse (CC0 / public domain / CC BY / CC BY-SA, commercial use and edits allowed).

Search results come from the public Openverse API (no key). A track is imported by its Openverse id: the
server looks it up again and downloads the file itself, so the browser never chooses the download URL.
"""
import json
import os
import re
import tempfile
from pathlib import Path
from urllib import request, error, parse
import ai33_audio as api
import asset_store
import audio_files

API = os.environ.get('REVIEW_OPENVERSE_URL', 'https://api.openverse.org/v1/').rstrip('/') + '/'
# Licences that allow use in a monetised video and editing (cutting, mixing). NC and ND are never offered.
LICENSES = {'cc0': 'CC0 · không cần ghi nguồn', 'pdm': 'Phạm vi công cộng', 'by': 'CC BY · cần ghi nguồn', 'by-sa': 'CC BY-SA · cần ghi nguồn'}
CATEGORIES = ('music', 'sound_effect', 'all')
ID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
LIMIT = 60 * 1024 * 1024


class MusicError(api.AudioError):
    def __init__(self, message, status=400):
        super().__init__(message, status)


def get(path, params=None):
    url = API + path + ('?' + parse.urlencode(params) if params else '')
    headers = {'Accept': 'application/json', 'User-Agent': 'ReviewStudio/' + audio_files.VERSION}
    try:
        with request.urlopen(request.Request(url, headers=headers), timeout=25) as response:
            data = json.loads(response.read(4 * 1024 * 1024))
    except error.HTTPError as exc:
        if exc.code == 429:
            raise MusicError('Openverse đang giới hạn số lượt tìm. Chờ khoảng 1 phút rồi thử lại.', 429) from None
        if exc.code == 404:
            raise MusicError('Không tìm thấy bản nhạc này trên Openverse nữa.', 404) from None
        raise MusicError(f'Openverse trả lỗi HTTP {exc.code}. Thử lại sau.', 502) from None
    except (error.URLError, TimeoutError, OSError):
        raise MusicError('Không kết nối được Openverse. Kiểm tra mạng/proxy rồi thử lại.', 504) from None
    except ValueError:
        raise MusicError('Openverse trả dữ liệu không hợp lệ.', 502) from None
    if not isinstance(data, dict):
        raise MusicError('Openverse trả dữ liệu không hợp lệ.', 502)
    return data


def credit(item):
    """Attribution line for the video caption: "Title" by Creator (licence) via source."""
    name = LICENSES.get(item.get('license'), '').split(' ·')[0]
    version = item.get('license_version') or ''
    parts = [f'"{item.get("title") or "Không tên"}"']
    if item.get('creator'):
        parts.append('của ' + str(item['creator']))
    parts.append(f'({name}{" " + version if version and item.get("license") not in ("cc0", "pdm") else ""})')
    if item.get('source'):
        parts.append('· ' + str(item['source']))
    return ' '.join(parts)[:300]


def clean(item):
    if not isinstance(item, dict) or not ID.fullmatch(str(item.get('id', ''))):
        return None
    if item.get('license') not in LICENSES or not str(item.get('url', '')).startswith('https://'):
        return None
    duration = item.get('duration')
    seconds = round(duration / 1000, 1) if isinstance(duration, (int, float)) and duration > 0 else None
    text = lambda key, limit=200: str(item.get(key) or '')[:limit]
    landing = text('foreign_landing_url', 500)
    return dict(id=item['id'], title=text('title') or 'Không tên', creator=text('creator'), license=item['license'],
                license_label=LICENSES[item['license']], license_url=text('license_url', 300), duration=seconds,
                preview=item['url'], landing=landing if landing.startswith('https://') else '', source=text('source', 60),
                genres=[str(g)[:30] for g in (item.get('genres') or [])][:4] if isinstance(item.get('genres'), list) else [],
                credit=credit(item), attribution_required=item['license'] in ('by', 'by-sa'))


def search(raw):
    query = raw.get('q', '')
    if not isinstance(query, str) or len(query) > 100:
        raise MusicError('Từ khóa tìm nhạc tối đa 100 ký tự.')
    page = raw.get('page', 1)
    if isinstance(page, bool) or not isinstance(page, int) or not 1 <= page <= 20:
        raise MusicError('Trang kết quả không hợp lệ.')
    category = raw.get('category', 'music')
    if category not in CATEGORIES:
        raise MusicError('Loại âm thanh không hợp lệ.')
    params = dict(q=' '.join(query.split()) or 'background music', page=page, page_size=20,
                  license_type='commercial,modification', mature='false')
    if category != 'all':
        params['category'] = category
    data = get('audio/', params)
    rows = [row for row in (clean(item) for item in data.get('results') or []) if row]
    count = data.get('result_count') if isinstance(data.get('result_count'), int) else len(rows)
    return dict(results=rows, page=page, pages=min(20, data.get('page_count') or 1) if isinstance(data.get('page_count'), int) else 1, count=count)


def fetch_file(url, target):
    audio_files.download(url, target, referer=None)


def fetch(raw, directory):
    """Import one Openverse track into the local MP3 library (re-validated server side)."""
    key = raw.get('id')
    if not isinstance(key, str) or not ID.fullmatch(key):
        raise MusicError('Mã bản nhạc không hợp lệ.')
    item = clean(get('audio/' + key + '/'))
    if not item:
        raise MusicError('Bản nhạc này không có giấy phép cho phép dùng thương mại và chỉnh sửa.')
    with tempfile.TemporaryDirectory(dir=directory) as folder:
        source = Path(folder) / 'track.download'
        fetch_file(item['preview'], source)
        if source.stat().st_size > LIMIT:
            raise MusicError('File nhạc lớn hơn 60 MB.')
        asset = audio_files.import_audio(source, directory, item['title'])
    record = asset_store.write(directory, asset['asset_id'], source='openverse', license=item['license_label'],
                               credit=item['credit'], source_url=item['landing'])
    return {**asset_store.public(record), 'attribution_required': item['attribution_required']}
