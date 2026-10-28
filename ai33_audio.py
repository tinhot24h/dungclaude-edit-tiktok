"""ai33.pro v3 TTS and voice library, based on the supplied API screenshots."""
import secrets_store
import json
import math
import os
import re
import socket
import time
import uuid
from urllib import request, error, parse

ROOT = 'https://api.ai33.pro'
PROVIDERS = ('elevenlabs','minimax','clone','edge','kokoro','vbee','fishaudio')
# Optional voice-library filters from the v3 docs (vbee/fishaudio specific ones are ignored by other providers).
FILTERS = ('tags','locale','age','accent','category','use_case','descriptive','voice_ownership','sort','tag')


class AudioError(Exception):
    def __init__(self,message,status=502):
        super().__init__(message)
        self.status=status


def configured():
    return bool(secrets_store.get('ai33') or os.environ.get('REVIEW_AI33_KEY') or os.environ.get('AI33_API_KEY'))


def api_key(raw):
    if not isinstance(raw,dict):
        raise ValueError('Yêu cầu âm thanh không hợp lệ.')
    key=raw.get('api_key') or secrets_store.get('ai33') or os.environ.get('REVIEW_AI33_KEY') or os.environ.get('AI33_API_KEY')
    if not key:
        raise AudioError('Nhập ai33.pro API key trong mục Âm thanh. Không gửi key trong chat.',400)
    if not isinstance(key,str) or len(key)>1024 or any(ord(c)<33 or ord(c)>126 for c in key):
        raise AudioError('API key ai33.pro có định dạng không hợp lệ.',400)
    return key


RETRY_WAITS=(3,10)


def json_request(path,key,data=None,content_type=None,method=None,timeout=80):
    """One ai33 request, tried again up to twice for a passing failure. Reading (GET) retries any network error,
    429 or 5xx. Creating (POST) retries only what proves nothing was created: the connection never opened, or
    429/503 (refused before work started), so a voice is never bought twice."""
    read=data is None and method in (None,'GET')
    for attempt in range(len(RETRY_WAITS)+1):
        try:return _request(path,key,data,content_type,method,timeout)
        except _Retry as retry:
            if attempt>=len(RETRY_WAITS) or not (read or retry.safe):raise retry.error from None
            time.sleep(RETRY_WAITS[attempt])


class _Retry(Exception):
    def __init__(self,error,safe):
        self.error=error;self.safe=safe


def _request(path,key,data=None,content_type=None,method=None,timeout=80):
    # Only documented paths are constructed by this module. Never put keys in URLs.
    req=request.Request(ROOT+path,data=data,headers={'xi-api-key':key,**({'Content-Type':content_type} if content_type else {})},method=method)
    try:
        with request.urlopen(req,timeout=timeout) as response:
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
        message,status=messages.get(exc.code,(f'Dịch vụ ai33.pro đang gặp lỗi (HTTP {exc.code}). Kiểm tra lịch sử tác vụ trước khi gửi lại yêu cầu tạo audio.',502))
        if exc.code==429 or exc.code>=500:raise _Retry(AudioError(message,status),exc.code in (429,503)) from None
        raise AudioError(message,status) from None
    except (error.URLError,socket.timeout,TimeoutError) as exc:
        message=('Không kết nối được ai33.pro hoặc hết thời gian chờ. Nếu vừa tạo audio, tác vụ có thể đã được nhận; '
                 'kiểm tra lịch sử ai33.pro trước khi bấm tạo lại để tránh trừ credit hai lần.')
        reason=getattr(exc,'reason',exc)
        refused=isinstance(exc,error.URLError) and isinstance(reason,(ConnectionRefusedError,socket.gaierror))
        raise _Retry(AudioError(message,504),refused) from None
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
    for field,default,limit in [('language','Vietnamese',100),('gender','',40),('search','',200),*[(f,'',100) for f in FILTERS]]:
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
        tags=item.get('tags') if isinstance(item.get('tags'),list) else []
        voices.append(dict(voice_id=item['voice_id'],name=str(item.get('name',item['voice_id']))[:300],
                           language=str(item.get('language',''))[:100],gender=str(item.get('gender',''))[:40],
                           tags=[str(t)[:40] for t in tags[:8]],description=str(item.get('description',''))[:300],
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
    return common_fields(raw,fields)


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
    return submitted(json_request('/v3/text-to-speech',key,body,content_type))


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
    srt=metadata.get('srt_url') or ''
    try:srt=https_url(srt) if srt else ''
    except AudioError:srt=''
    # /v1/task/dubbing: the SRT re-voiced with the chosen voice (voice only, timed like the source)
    replacement=metadata.get('replacement_audio_url') or ''
    try:replacement=https_url(replacement) if replacement else ''
    except AudioError:replacement=''
    return dict(task_id=task,status=status,progress=max(0,min(100,progress)),audio_url=audio,srt_url=srt,
                replacement_audio_url=replacement,replacement_status=str(metadata.get('replacement_status') or '')[:40],
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
        cost=row.get('credit_cost')
        tasks.append(dict(task_id=row['id'],status=str(row.get('status',''))[:30],progress=row.get('progress') if isinstance(row.get('progress'),(int,float)) and not isinstance(row.get('progress'),bool) else None,
                          credit_cost=cost if isinstance(cost,(int,float)) and not isinstance(cost,bool) and math.isfinite(cost) else None,
                          srt_available=bool(md.get('srt_url')),
                          created_at=str(row.get('created_at',''))[:80],type=str(row.get('type',''))[:80],
                          text=str(row.get('text',''))[:1000],name=str(row.get('file_name') or md.get('file_name') or row.get('name') or '')[:120],
                          audio_available=bool((row.get('metadata') or {}).get('audio_url')) if isinstance(row.get('metadata'),dict) else False))
    return dict(tasks=tasks,page=page,has_more=isinstance(result.get('total'),int) and page*20<result['total'])


def find_task(raw,task,pages=5):
    """Look a task up in the history (/v1/tasks) — a fallback when /v1/task/<id> fails although the audio exists."""
    key=api_key(raw)
    for page in range(1,pages+1):
        result=json_request('/v1/tasks?'+parse.urlencode(dict(page=page,limit=20)),key,content_type='application/json')
        rows=result.get('data') if isinstance(result.get('data'),list) else []
        for row in rows:
            if isinstance(row,dict) and row.get('id')==task:
                md=row.get('metadata') if isinstance(row.get('metadata'),dict) else {}
                audio=md.get('audio_url') or ''
                try:audio=https_url(audio) if audio else ''
                except AudioError:audio=''
                srt=md.get('srt_url') or ''
                try:srt=https_url(srt) if srt else ''
                except AudioError:srt=''
                status=row.get('status') if row.get('status') in ('doing','done','error') else ('done' if audio else 'doing')
                return dict(task_id=task,status=status,audio_url=audio,srt_url=srt)
        if not rows or not (isinstance(result.get('total'),int) and page*20<result['total']):break
    return None


def common_fields(raw,fields):
    """with_transcript, file_name and pronunciation_dictionary_id are shared by TTS and dialogue."""
    transcript=raw.get('with_transcript',False)
    if not isinstance(transcript,bool):
        raise ValueError('Tùy chọn transcript không hợp lệ.')
    fields['with_transcript']=str(transcript).lower()
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
    return fields


VOICE=r'(?:elevenlabs|minimax|clone|edge|kokoro|vbee|fishaudio)_[^\s\x00-\x1f]+'
LABEL=re.compile(r'^\s*([A-Z])>',re.M)


def dialogue_fields(raw):
    if not isinstance(raw,dict):
        raise ValueError('Yêu cầu hội thoại không hợp lệ.')
    text=raw.get('text')
    if not isinstance(text,str) or not 1<=len(text.strip())<=1000000:
        raise ValueError('Văn bản hội thoại phải từ 1 đến 1.000.000 ký tự.')
    speakers=raw.get('speakers')
    if not isinstance(speakers,list) or not 2<=len(speakers)<=26:
        raise ValueError('Hội thoại cần từ 2 đến 26 người nói.')
    rows=[]
    for item in speakers:
        if not isinstance(item,dict) or not isinstance(item.get('voice_id'),str) or len(item['voice_id'])>500 or not re.fullmatch(VOICE,item['voice_id']):
            raise ValueError('Mỗi người nói cần voice_id có prefix nhà cung cấp.')
        speed=item.get('speed',1)
        if isinstance(speed,bool) or not isinstance(speed,(int,float)) or not math.isfinite(speed) or not .5<=speed<=1.5:
            raise ValueError('Tốc độ người nói phải nằm trong khoảng 0,5–1,5.')
        rows.append(dict(voice_id=item['voice_id'],speed=speed))
    labels=sorted(set(LABEL.findall(text)))
    if not labels:
        raise ValueError('Đánh dấu từng câu bằng nhãn A>, B>, C>… ở đầu dòng.')
    if any(ord(label)-65>=len(rows) for label in labels):
        raise ValueError(f'Văn bản dùng nhãn {labels[-1]}> nhưng mới có {len(rows)} người nói. Thêm người nói hoặc sửa nhãn.')
    delay=raw.get('delay',0)
    if isinstance(delay,bool) or not isinstance(delay,(int,float)) or not math.isfinite(delay) or not 0<=delay<=5:
        raise ValueError('Khoảng nghỉ giữa người nói phải từ 0 đến 5 giây.')
    fields=dict(text=text.strip(),speakers=json.dumps(rows,ensure_ascii=False),delay=str(delay))
    return common_fields(raw,fields)


DUB_LANGS=('auto','zh','en','vi','ja','ko','fr','de','es','th','id')
# /v1/task/dubbing requires receive_url, but this local app polls GET /v1/task instead. The callback goes to a
# reserved .invalid name that never resolves, so the result payload is not delivered anywhere.
RECEIVE_URL='https://review-studio.invalid/ai33-callback'


def create_dubbing(key,audio,source_lang='auto',target_lang='vi',voice_id='',num_speakers=0):
    """Dub an MP3 (ai33 transcribes, translates and returns a timed SRT); with voice_id the SRT is synthesized once
    more with that voice as a voice-only track (replacement_audio_url). Sent once; never retried automatically."""
    key=api_key(dict(api_key=key))
    if source_lang not in DUB_LANGS or target_lang not in DUB_LANGS or target_lang=='auto':
        raise ValueError('Ngôn ngữ lồng tiếng ai33 không hợp lệ.')
    if voice_id and (not isinstance(voice_id,str) or not re.fullmatch(r'(elevenlabs|minimax|clone|edge|vbee|fishaudio)_[A-Za-z0-9_.:-]{1,180}',voice_id)):
        raise ValueError('Giọng này không dùng được cho lồng tiếng ai33 (Kokoro không hỗ trợ).')
    fields=dict(num_speakers=str(int(num_speakers)),disable_voice_cloning='true',source_lang=source_lang,target_lang=target_lang,receive_url=RECEIVE_URL)
    if voice_id:fields['voice_id']=voice_id
    boundary='ReviewStudio'+uuid.uuid4().hex
    pieces=[]
    for name,value in fields.items():
        pieces.extend([f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),value.encode('utf-8'),b'\r\n'])
    pieces.extend([f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="audio.mp3"\r\nContent-Type: audio/mpeg\r\n\r\n'.encode(),audio,b'\r\n',f'--{boundary}--\r\n'.encode()])
    return submitted(json_request('/v1/task/dubbing',key,b''.join(pieces),'multipart/form-data; boundary='+boundary,timeout=300))


def submitted(result):
    task=result.get('task_id')
    if result.get('success') is not True or not isinstance(task,str) or not task.strip() or len(task)>200 or not re.fullmatch('[A-Za-z0-9_-]+',task):
        raise AudioError('ai33.pro chưa trả task_id hợp lệ. Kiểm tra lịch sử tác vụ trước khi tạo lại để tránh trừ credit trùng.')
    return dict(task_id=task,state='submitted')


def create_dialogue(raw):
    fields=dialogue_fields(raw)
    key=api_key(raw)
    body,content_type=form_data(fields)
    return submitted(json_request('/v3/text-to-speech/dialogue',key,body,content_type))


# ---- Pronunciation dictionaries (/v3/dictionaries, JSON body)

def rules(value):
    if not isinstance(value,list) or not 1<=len(value)<=500:
        raise ValueError('Từ điển cần từ 1 đến 500 quy tắc.')
    out=[]
    for rule in value:
        if not isinstance(rule,dict):
            raise ValueError('Quy tắc phát âm không hợp lệ.')
        source,target=rule.get('from'),rule.get('to')
        match=rule.get('matchType','word');case=rule.get('caseSensitive',False)
        if not isinstance(source,str) or not 1<=len(source.strip())<=200 or not isinstance(target,str) or len(target)>200:
            raise ValueError('Mỗi quy tắc cần chữ gốc (1–200 ký tự) và cách đọc (tối đa 200 ký tự).')
        if match not in ('word','contains') or not isinstance(case,bool):
            raise ValueError('matchType chỉ nhận word hoặc contains; caseSensitive là đúng/sai.')
        out.append({'from':source.strip(),'to':target.strip(),'matchType':match,'caseSensitive':case})
    return out


def dictionary_row(item):
    if not isinstance(item,dict) or isinstance(item.get('id'),bool) or not isinstance(item.get('id'),int):
        return None
    raw=item.get('rules') if isinstance(item.get('rules'),list) else []
    clean=[]
    for rule in raw[:500]:
        if isinstance(rule,dict) and isinstance(rule.get('from'),str):
            clean.append({'from':rule['from'][:200],'to':str(rule.get('to',''))[:200],'matchType':rule.get('matchType') if rule.get('matchType') in ('word','contains') else 'word','caseSensitive':rule.get('caseSensitive') is True})
    return dict(id=item['id'],name=str(item.get('name',''))[:120],rules=clean)


def dictionary_id(raw):
    value=raw.get('id') if isinstance(raw,dict) else None
    if isinstance(value,bool) or not isinstance(value,int) or not 1<=value<=9007199254740991:
        raise ValueError('ID từ điển không hợp lệ.')
    return value


def dictionaries(raw):
    result=json_request('/v3/dictionaries',api_key(raw),content_type='application/json')
    rows=next((result[k] for k in ('data','dictionaries','items') if isinstance(result.get(k),list)),None)
    if rows is None:
        raise AudioError('Danh sách từ điển ai33.pro không hợp lệ.')
    return dict(dictionaries=[r for r in map(dictionary_row,rows) if r])


def unwrap(result):
    for key in ('dictionary','data'):
        if isinstance(result.get(key),dict):
            return result[key]
    return result


def save_dictionary(raw):
    key=api_key(raw)
    name=raw.get('name')
    if not isinstance(name,str) or not 1<=len(name.strip())<=120:
        raise ValueError('Tên từ điển cần từ 1 đến 120 ký tự.')
    body=json.dumps(dict(name=name.strip(),rules=rules(raw.get('rules'))),ensure_ascii=False).encode()
    if raw.get('id') is None:
        result=json_request('/v3/dictionaries',key,body,'application/json')
    else:
        result=json_request(f'/v3/dictionaries/{dictionary_id(raw)}',key,body,'application/json','PUT')
    row=dictionary_row(unwrap(result))
    if not row:
        raise AudioError('ai33.pro chưa trả từ điển hợp lệ sau khi lưu.')
    return row


def delete_dictionary(raw):
    json_request(f'/v3/dictionaries/{dictionary_id(raw)}',api_key(raw),content_type='application/json',method='DELETE')
    return dict(deleted=True)


def preview_dictionary(raw):
    text=raw.get('text')
    if not isinstance(text,str) or not 1<=len(text)<=5000:
        raise ValueError('Văn bản thử cần từ 1 đến 5.000 ký tự.')
    body=json.dumps(dict(text=text,rules=rules(raw.get('rules'))),ensure_ascii=False).encode()
    result=unwrap(json_request('/v3/dictionaries/preview',api_key(raw),body,'application/json'))
    output=result.get('output')
    if not isinstance(output,str):
        raise AudioError('ai33.pro chưa trả kết quả xem trước từ điển.')
    return dict(input=str(result.get('input',text))[:5000],output=output[:5000])


# ---- Voice cloning (/v3/text-to-speech/voice-clone)

def clone_voice(key,name,filename,data):
    if not isinstance(name,str) or not 1<=len(name.strip())<=100 or any(ord(c)<32 for c in name):
        raise ValueError('Tên giọng nhân bản cần từ 1 đến 100 ký tự.')
    if not 0<len(data)<=10*1024*1024:
        raise ValueError('File mẫu giọng tối đa 10 MB.')
    boundary='ReviewStudio'+uuid.uuid4().hex
    safe=re.sub(r'[^A-Za-z0-9._-]','_',filename or 'sample.mp3')[-80:] or 'sample.mp3'
    body=b''.join([f'--{boundary}\r\nContent-Disposition: form-data; name="voice_name"\r\n\r\n'.encode(),name.strip().encode('utf-8'),b'\r\n',
                   f'--{boundary}\r\nContent-Disposition: form-data; name="audio_file"; filename="{safe}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode(),data,b'\r\n',
                   f'--{boundary}--\r\n'.encode()])
    result=json_request('/v3/text-to-speech/voice-clone',api_key({'api_key':key}),body,'multipart/form-data; boundary='+boundary)
    voice=unwrap(result).get('voice_id')
    if isinstance(voice,int) and not isinstance(voice,bool):voice=str(voice)
    if not isinstance(voice,str) or not re.fullmatch('[A-Za-z0-9_-]{1,200}',voice):
        raise AudioError('ai33.pro chưa trả voice_id cho giọng nhân bản.')
    return dict(voice_id=voice if voice.startswith('clone_') else 'clone_'+voice,name=name.strip())


def delete_clone(raw):
    voice=raw.get('voice_id') if isinstance(raw,dict) else None
    if not isinstance(voice,str) or not re.fullmatch('(?:clone_)?[A-Za-z0-9_-]{1,200}',voice):
        raise ValueError('voice_id giọng nhân bản không hợp lệ.')
    json_request('/v3/text-to-speech/voice-clone/'+parse.quote(voice.removeprefix('clone_'),safe=''),api_key(raw),content_type='application/json',method='DELETE')
    return dict(deleted=True)
