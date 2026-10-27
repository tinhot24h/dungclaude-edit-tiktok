"""Saved projects and design templates as small local JSON files; no media is copied."""
import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

KINDS=('projects','templates','styles')
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
            rows.append({k:record.get(k,'') for k in ('id','kind','name','updated_at')})
    return sorted(rows,key=lambda r:r['updated_at'],reverse=True)[:200]


def delete(root,kind,key):
    path=folder(root,kind)/(valid_id(key)+'.json')
    if not path.is_file():raise ValueError('Không tìm thấy dự án đã lưu.')
    path.unlink()
