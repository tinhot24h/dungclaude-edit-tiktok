"""Saved projects and design templates as small local JSON files; no media is copied."""
import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

KINDS=('projects','templates','styles','presets','dubpresets','buildpresets')
LIMIT=512*1024
LOCK=threading.Lock()


def folder(root,kind):
    if kind not in KINDS:raise ValueError('Loại thư viện không hợp lệ.')
    path=Path(root)/kind;path.mkdir(parents=True,exist_ok=True)
    return path


def valid_id(value):
    if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{32}',value):raise ValueError('Mã dự án không hợp lệ.')
    return value


def save(root,kind,raw):
    if not isinstance(raw,dict) or not isinstance(raw.get('data'),dict):raise ValueError('Dữ liệu dự án không hợp lệ.')
    name=raw.get('name')
    if not isinstance(name,str) or not 1<=len(name.strip())<=120:raise ValueError('Tên cần từ 1 đến 120 ký tự.')
    key=raw.get('id') or uuid.uuid4().hex
    valid_id(key)
    record=dict(id=key,kind=kind,name=' '.join(name.split()),updated_at=datetime.now(timezone.utc).isoformat(),data=raw['data'])
    text=json.dumps(record,ensure_ascii=False)
    if len(text.encode())>LIMIT:raise ValueError('Dự án quá lớn để lưu (tối đa 512 KB).')
    path=folder(root,kind)/(key+'.json')
    with LOCK:
        tmp=path.with_suffix('.json.tmp');tmp.write_text(text,encoding='utf-8');tmp.replace(path)
    return {k:record[k] for k in ('id','kind','name','updated_at')}


def read(root,kind,key):
    try:record=json.loads((folder(root,kind)/(valid_id(key)+'.json')).read_text(encoding='utf-8'))
    except (OSError,ValueError):raise ValueError('Không tìm thấy dự án đã lưu.') from None
    if not isinstance(record,dict) or not isinstance(record.get('data'),dict):raise ValueError('File dự án bị hỏng.')
    return record


def items(root,kind):
    rows=[]
    for path in folder(root,kind).glob('*.json'):
        try:record=json.loads(path.read_text(encoding='utf-8'))
        except (OSError,ValueError):continue
        if isinstance(record,dict) and record.get('id')==path.stem:
            row={k:record.get(k,'') for k in ('id','kind','name','updated_at')}
            meta=record['data'].get('meta') if isinstance(record.get('data'),dict) else None
            if isinstance(meta,dict):row['meta']=meta   # presets: their parts, description, last use (the list needs no second read)
            rows.append(row)
    return sorted(rows,key=lambda r:r['updated_at'],reverse=True)[:200]


def delete(root,kind,key):
    path=folder(root,kind)/(valid_id(key)+'.json')
    if not path.is_file():raise ValueError('Không tìm thấy dự án đã lưu.')
    path.unlink()


def merge_build_presets(root):
    """0.22: "Dựng video" and "Lồng tiếng" share one tab and one list. Saved build templates move into the
    dub list (same id) as MP3-voice presets; nothing is copied twice."""
    moved=0
    for path in sorted(folder(root,'buildpresets').glob('*.json')):
        try:record=json.loads(path.read_text(encoding='utf-8'))
        except (OSError,ValueError):continue
        if not isinstance(record,dict) or not isinstance(record.get('data'),dict) or record.get('id')!=path.stem:continue
        target=folder(root,'dubpresets')/path.name
        if not target.exists():
            settings=record['data'].get('settings')
            if isinstance(settings,dict):settings.setdefault('voice_source','mp3' if settings.get('mode')=='design' else 'ai33')
            record['kind']='dubpresets';record['name']=('Mẫu dựng · '+str(record.get('name','')))[:120]
            with LOCK:
                tmp=target.with_suffix('.json.tmp');tmp.write_text(json.dumps(record,ensure_ascii=False),encoding='utf-8');tmp.replace(target)
            moved+=1
        path.unlink(missing_ok=True)
    return moved
