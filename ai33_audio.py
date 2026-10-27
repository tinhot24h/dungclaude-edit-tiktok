"""ai33.pro v3 TTS and voice library, based on the supplied API screenshots."""
import json
import math
import os
import re
import socket
import uuid
from urllib import request, error, parse

ROOT = 'https://api.ai33.pro'
PROVIDERS = ('elevenlabs','minimax','clone','edge','kokoro','vbee','fishaudio')


class AudioError(Exception):
    def __init__(self,message,status=502):
        super().__init__(message)
        self.status=status


def configured():
    return bool(os.environ.get('REVIEW_AI33_KEY') or os.environ.get('AI33_API_KEY'))


def api_key(raw):
    if not isinstance(raw,dict):
        raise ValueError('Yêu cầu âm thanh không hợp lệ.')
    key=raw.get('api_key') or os.environ.get('REVIEW_AI33_KEY') or os.environ.get('AI33_API_KEY')
    if not key:
        raise AudioError('Nhập ai33.pro API key trong mục Âm thanh. Không gửi key trong chat.',400)
    if not isinstance(key,str) or len(key)>1024 or any(ord(c)<33 or ord(c)>126 for c in key):
        raise AudioError('API key ai33.pro có định dạng không hợp lệ.',400)
    return key


def json_request(path,key,data=None,content_type=None):
    # Only documented paths are constructed by this module. Never put keys in URLs.
    req=request.Request(ROOT+path,data=data,headers={'xi-api-key':key,**({'Content-Type':content_type} if content_type else {})})
    try:
        with request.urlopen(req,timeout=80) as response:
            body=response.read(8*1024*1024+1)
        if len(body)>8*1024*1024:
            raise AudioError('Phản hồi ai33.pro quá lớn.')
        result=json.loads(body)
        if not isinstance(result,dict):
            raise ValueError()
        if result.get('success') is False:
            # Provider errors can contain request details; do not echo them with a key.
            raise AudioError('ai33.pro báo yêu cầu thất bại. Kiểm tra key, quyền dùng giọng và credit trong tài khoản.',400)
        return result
    except error.HTTPError as exc:
        messages={400:('ai33.pro không chấp nhận dữ liệu. Kiểm tra voice_id có prefix, tốc độ và nội dung.',400),
                  401:('ai33.pro API key không hợp lệ hoặc hết hiệu lực.',401),
                  402:('ai33.pro báo không đủ credit. Kiểm tra số dư của tài khoản.',402),
                  403:('ai33.pro từ chối key hoặc quyền truy cập tài nguyên.',403),
                  404:('Không tìm thấy tài nguyên ai33.pro. Kiểm tra giọng hoặc task_id.',404),
                  429:('ai33.pro báo quá nhiều yêu cầu. Chờ rồi kiểm tra lại, không tạo thêm tác vụ trùng.',429)}
        message,status=messages.get(exc.code,('Dịch vụ ai33.pro đang gặp lỗi. Kiểm tra lịch sử tác vụ trước khi gửi lại yêu cầu tạo audio.',502))
        raise AudioError(message,status) from None
    except (error.URLError,socket.timeout,TimeoutError):
        message=('Không kết nối được ai33.pro hoặc hết thời gian chờ. Nếu vừa tạo audio, tác vụ có thể đã được nhận; '
                 'kiểm tra lịch sử ai33.pro trước khi bấm tạo lại để tránh trừ credit hai lần.')
        raise AudioError(message,504) from None
    except (json.JSONDecodeError,ValueError,TypeError):
        raise AudioError('Không đọc được phản hồi ai33.pro. Nếu đã gửi tạo audio, kiểm tra lịch sử tác vụ trước khi tạo lại.') from None


def voice_library(raw):
    key=api_key(raw)
    provider=raw.get('provider','edge')
    if provider not in PROVIDERS:
        raise ValueError('Nhà cung cấp giọng không hợp lệ.')
    page=raw.get('page',1)
    if isinstance(page,bool) or not isinstance(page,int) or not 1<=page<=100000:
        raise ValueError('Trang danh sách giọng không hợp lệ.')
    size=raw.get('page_size',30)
    if isinstance(size,bool) or not isinstance(size,int) or not 1<=size<=100:raise ValueError('Số giọng mỗi trang phải từ 1 đến 100.')
    query=dict(provider=provider,page=page,page_size=size)
    for field,default,limit in [('language','Vietnamese',100),('gender','',40),('search','',200)]:
        value=raw.get(field,default)
        if not isinstance(value,str) or len(value)>limit:
            raise ValueError('Bộ lọc giọng không hợp lệ.')
        if value.strip():
            query[field]=value.strip()
    result=json_request('/v3/voices?'+parse.urlencode(query),key)
    rows=result.get('data')
    if not isinstance(rows,list):
        raise AudioError('Thư viện giọng trả về định dạng không hợp lệ.')
    voices=[]
    for item in rows:
        if not isinstance(item,dict) or not isinstance(item.get('voice_id'),str):
            continue
        preview=item.get('preview_url')
        try:
            preview=https_url(preview) if preview else ''
        except AudioError:
            preview=''
        voices.append(dict(voice_id=item['voice_id'],name=str(item.get('name',item['voice_id']))[:300],
                           language=str(item.get('language',''))[:100],gender=str(item.get('gender',''))[:40],
                           preview_url=preview))
    pagination=result.get('pagination',{})
    pagination=pagination if isinstance(pagination,dict) else {}
    total=pagination.get('total',result.get('total'))
    actual_size=pagination.get('page_size',pagination.get('limit',size))
    if isinstance(actual_size,bool) or not isinstance(actual_size,int) or actual_size<1:actual_size=size
    size=actual_size
    more=bool(rows) and (bool(pagination.get('has_more')) if 'has_more' in pagination else (page*size<total if isinstance(total,int) else len(rows)>=size))
    return dict(voices=voices,page=page,page_size=size,total=total,has_more=more)


def tts_fields(raw):
    if not isinstance(raw,dict):
        raise ValueError('Yêu cầu tạo audio không hợp lệ.')
    text=raw.get('text')
    voice=raw.get('voice_id')
    speed=raw.get('speed',1)
    transcript=raw.get('with_transcript',False)
    if not isinstance(text,str) or not 1<=len(text.strip())<=1000000:
        raise ValueError('Văn bản tạo giọng phải từ 1 đến 1.000.000 ký tự.')
    if not isinstance(voice,str) or len(voice)>500 or not re.fullmatch(r'(?:elevenlabs|minimax|clone|edge|kokoro|vbee|fishaudio)_[^\s\x00-\x1f]+',voice):
        raise ValueError('voice_id cần prefix elevenlabs_, minimax_, clone_, edge_, kokoro_, vbee_ hoặc fishaudio_.')
    if isinstance(speed,bool) or not isinstance(speed,(float,int)) or not math.isfinite(speed) or not .5<=speed<=1.5:
        raise ValueError('Tốc độ phải nằm trong khoảng 0,5–1,5.')
    if not isinstance(transcript,bool):
        raise ValueError('Tùy chọn transcript không hợp lệ.')
    fields=dict(text=text.strip(),voice_id=voice,speed=str(speed),with_transcript=str(transcript).lower())
    dictionary=raw.get('pronunciation_dictionary_id')
    if dictionary not in (None,''):
        if isinstance(dictionary,bool) or not isinstance(dictionary,int) or not 1<=dictionary<=9007199254740991:
            raise ValueError('ID từ điển phát âm phải là số nguyên dương.')
        fields['pronunciation_dictionary_id']=str(dictionary)
    filename=raw.get('file_name','')
    if not isinstance(filename,str) or len(filename)>120 or '\n' in filename or '\r' in filename:
        raise ValueError('Tên file audio không hợp lệ.')
    if filename.strip():
        fields['file_name']=filename.strip()
    # No receive_url: a local desktop app cannot receive a public webhook.
    return fields


def form_data(fields):
    boundary='ReviewStudio'+uuid.uuid4().hex
    pieces=[]
    for name,value in fields.items():
        pieces.extend([f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),value.encode('utf-8'),b'\r\n'])
    pieces.append(f'--{boundary}--\r\n'.encode())
    return b''.join(pieces),'multipart/form-data; boundary='+boundary


def create_tts(raw):
    fields=tts_fields(raw)
    key=api_key(raw)
    body,content_type=form_data(fields)
    result=json_request('/v3/text-to-speech',key,body,content_type)
    task=result.get('task_id')
    if result.get('success') is not True or not isinstance(task,str) or not task.strip() or len(task)>200 or not re.fullmatch('[A-Za-z0-9_-]+',task):
        raise AudioError('ai33.pro chưa trả task_id hợp lệ. Kiểm tra lịch sử tác vụ trước khi tạo lại để tránh trừ credit trùng.')
    return dict(task_id=task,state='submitted')


def task_id(raw):
    value=raw.get('task_id') if isinstance(raw,dict) else None
    if not isinstance(value,str) or not re.fullmatch('[A-Za-z0-9_-]{1,200}',value):
        raise ValueError('task_id không hợp lệ.')
    return value


def https_url(value):
    """Accept HTTPS media locations, never credentials or obvious private hosts."""
    import ipaddress
    if not isinstance(value,str) or len(value)>16000:
        raise AudioError('Link audio từ ai33.pro không hợp lệ.')
    try:
        parts=parse.urlsplit(value)
        host=(parts.hostname or '').rstrip('.').lower()
        if parts.scheme!='https' or not host or parts.username or parts.password or parts.port not in (None,443):
            raise ValueError()
        if any(ord(c)<33 or ord(c)>126 for c in value) or host=='localhost' or host.endswith(('.localhost','.local','.internal','.home.arpa')):
            raise ValueError()
        try:
            ip=ipaddress.ip_address(host)
        except ValueError:
            if '.' not in host:
                raise ValueError()
        else:
            if not ip.is_global:
                raise ValueError()
    except ValueError:
        raise AudioError('Chỉ chấp nhận link audio HTTPS công khai, không có thông tin đăng nhập.') from None
    return value


def get_task(raw):
    key=api_key(raw)
    task=task_id(raw)
    result=json_request('/v1/task/'+parse.quote(task,safe=''),key,content_type='application/json')
    if result.get('id') not in (None,task):
        raise AudioError('Phản hồi ai33.pro không khớp task_id đã yêu cầu.')
    status=result.get('status')
    if status not in ('doing','done','error'):
        raise AudioError('ai33.pro trả trạng thái tác vụ chưa nhận diện. Kiểm tra task_id trong lịch sử.')
    metadata=result.get('metadata') or {}
    if not isinstance(metadata,dict):
        raise AudioError('Metadata tác vụ ai33.pro không hợp lệ.')
    progress=result.get('progress',100 if status=='done' else 0)
    if isinstance(progress,bool) or not isinstance(progress,(int,float)) or not math.isfinite(progress):
        progress=0
    cost=result.get('credit_cost')
    if isinstance(cost,bool) or not isinstance(cost,(int,float)) or not math.isfinite(cost):
        cost=None
    audio=metadata.get('audio_url') or ''
    if audio:
        audio=https_url(audio)
    return dict(task_id=task,status=status,progress=max(0,min(100,progress)),audio_url=audio,
                credit_cost=cost,type=str(result.get('type',''))[:80],
                text=str(result.get('text',''))[:1000],name=str(result.get('file_name') or metadata.get('file_name') or metadata.get('filename') or result.get('name') or '')[:120],
                error='ai33.pro báo lỗi tác vụ. Xem chi tiết trong lịch sử ai33.pro; không tạo lại tự động.' if status=='error' else '')


def credits(raw):
    result=json_request('/v1/credits',api_key(raw),content_type='application/json')
    value=result.get('credits')
    if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value):
        raise AudioError('ai33.pro không trả số dư credit hợp lệ.')
    return dict(credits=value)


def list_tasks(raw):
    page=raw.get('page',1) if isinstance(raw,dict) else 1
    if isinstance(page,bool) or not isinstance(page,int) or not 1<=page<=100000:
        raise ValueError('Trang lịch sử không hợp lệ.')
    result=json_request('/v1/tasks?'+parse.urlencode(dict(page=page,limit=20)),api_key(raw),content_type='application/json')
    rows=result.get('data')
    if not isinstance(rows,list):
        raise AudioError('Lịch sử ai33.pro không hợp lệ.')
    tasks=[]
    for row in rows:
        if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not re.fullmatch('[A-Za-z0-9_-]{1,200}',row['id']):
            continue
        md=row.get('metadata') if isinstance(row.get('metadata'),dict) else {}
        tasks.append(dict(task_id=row['id'],status=str(row.get('status',''))[:30],
                          created_at=str(row.get('created_at',''))[:80],type=str(row.get('type',''))[:80],
                          text=str(row.get('text',''))[:1000],name=str(row.get('file_name') or md.get('file_name') or row.get('name') or '')[:120],
                          audio_available=bool((row.get('metadata') or {}).get('audio_url')) if isinstance(row.get('metadata'),dict) else False))
    return dict(tasks=tasks,page=page,has_more=isinstance(result.get('total'),int) and page*20<result['total'])
