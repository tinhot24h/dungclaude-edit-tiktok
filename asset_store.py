"""Local media catalog; stores names/task IDs, never keys or signed media URLs."""
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

LOCK=threading.RLock()


def clean_name(value,default='review-audio'):
    value=str(value or '').replace('\\','/').rsplit('/',1)[-1]
    value=re.sub(r'[\x00-\x1f<>:"|?*]','_',value).strip(' .')[:120]
    return value or default


def write(directory,aid,**data):
    if not re.fullmatch('[a-f0-9]{32}',aid):raise ValueError('Asset ID không hợp lệ.')
    directory=Path(directory);directory.mkdir(exist_ok=True)
    path=directory/(aid+'.json')
    with LOCK:
        old={}
        try:old=json.loads(path.read_text(encoding='utf-8'))
        except (OSError,ValueError):pass
        if not isinstance(old,dict):old={}
        allowed=('name','source','task_id','duration','bytes','created_at','voice_id','license','credit','source_url')
        old.update({k:v for k,v in data.items() if k in allowed})
        old.setdefault('created_at',datetime.now(timezone.utc).isoformat())
        old['asset_id']=aid;old['name']=clean_name(old.get('name'))
        tmp=directory/(aid+'.json.tmp');tmp.write_text(json.dumps(old,ensure_ascii=False),encoding='utf-8');tmp.replace(path)
    return old


def read(directory,aid):
    if not isinstance(aid,str) or not re.fullmatch('[a-f0-9]{32}',aid):raise ValueError('Asset ID không hợp lệ.')
    try:
        item=json.loads((Path(directory)/(aid+'.json')).read_text(encoding='utf-8'))
        return item if isinstance(item,dict) else {}
    except (OSError,ValueError):return {}


def public(item):
    return {**item,'url':'/audio/file/'+item['asset_id']}


def assets(directory):
    directory=Path(directory);items=[]
    for path in directory.glob('*.json'):
        if not re.fullmatch('[a-f0-9]{32}',path.stem) or not path.with_suffix('.mp3').is_file():continue
        item=read(directory,path.stem)
        if item and isinstance(item.get('duration'),(int,float)) and item['duration']>0:items.append(public(item))
    return sorted(items,key=lambda x:x.get('created_at',''),reverse=True)
