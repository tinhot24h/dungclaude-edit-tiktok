"""Download provider-returned media without API keys, validate and cache as MP3."""
import hashlib
import ipaddress
import json
import math
from pathlib import Path
import socket
import subprocess
import threading
import time
from urllib import request, error, parse
import ai33_audio as api
import asset_store
import ssl
import os
import uuid
import tempfile
import errno
from http.client import HTTPException

LIMIT=100*1024*1024
VERSION=(Path(__file__).resolve().parent/'VERSION').read_text(encoding='utf-8').strip()
_LOCKS={}
_MUTEX=threading.Lock()


def asset_id(task):
    return hashlib.sha256(task.encode('utf-8')).hexdigest()[:32]


def public_url(url):
    api.https_url(url)
    host=parse.urlsplit(url).hostname
    try:
        addresses=socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
    except OSError:
        raise api.AudioError('[AUDIO_DNS] Không phân giải được máy chủ audio. Kiểm tra DNS/proxy hoặc mở audio gốc bằng trình duyệt.') from None
    if not addresses or any(not ipaddress.ip_address(item[4][0].split('%')[0]).is_global for item in addresses):
        raise api.AudioError('Từ chối tải audio từ địa chỉ mạng nội bộ.')
    return url


class PublicRedirect(request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        public_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def download(url,target):
    public_url(url)
    opener=request.build_opener(PublicRedirect())
    deadline=time.monotonic()+180
    headers={'Accept':'audio/mpeg,audio/*,application/octet-stream;q=0.9,*/*;q=0.5',
             'User-Agent':'ReviewStudio/'+VERSION,'Referer':'https://ai33.pro/'}
    try:
        with opener.open(request.Request(url,headers=headers),timeout=60) as response:
            declared=response.headers.get('Content-Length')
            if declared and declared.isdigit() and int(declared)>LIMIT:
                raise api.AudioError('File audio vượt giới hạn tải 100 MB.')
            total=0
            with target.open('wb') as output:
                while True:
                    if time.monotonic()>deadline:raise api.AudioError('[DOWNLOAD_TIMEOUT] Tải quá 180 giây. Kiểm tra lại tác vụ hoặc mở link gốc trong trình duyệt.')
                    chunk=response.read(256*1024)
                    if not chunk:break
                    total+=len(chunk)
                    if total>LIMIT:raise api.AudioError('File audio vượt giới hạn tải 100 MB.')
                    output.write(chunk)
        if not total:raise api.AudioError('[EMPTY_AUDIO] Máy chủ trả file trống. Kiểm tra lại tác vụ, không tạo lại audio.')
    except error.HTTPError as exc:
        raise api.AudioError(f'[AUDIO_HTTP_{exc.code}] Máy chủ audio trả HTTP {exc.code}. Link có thể hết hạn hoặc CDN chặn ứng dụng. Kiểm tra lại để lấy link mới, hoặc mở audio gốc bằng trình duyệt; không tạo lại TTS.',502) from None
    except error.URLError as exc:
        if isinstance(exc.reason,ssl.SSLCertVerificationError):
            raise api.AudioError('[AUDIO_TLS] Không xác minh được chứng chỉ máy chủ audio. Kiểm tra chứng chỉ/mạng của máy hoặc mở audio gốc bằng trình duyệt. Không tắt kiểm tra TLS.',502) from None
        raise api.AudioError('[AUDIO_NETWORK] Không kết nối được máy chủ audio. Kiểm tra mạng/proxy hoặc mở link gốc bằng trình duyệt, không tạo lại TTS.',504) from None
    except TimeoutError:
        raise api.AudioError('[AUDIO_TIMEOUT] Máy chủ audio hết thời gian chờ. Kiểm tra lại tác vụ hoặc tải bằng trình duyệt.',504) from None
    except ssl.SSLError:
        raise api.AudioError('[AUDIO_TLS] Kết nối TLS tới máy chủ audio thất bại. Kiểm tra mạng/chứng chỉ hoặc dùng trình duyệt, không tắt xác minh TLS.',502) from None
    except (ConnectionError,HTTPException):
        raise api.AudioError('[AUDIO_TRANSFER] Máy chủ ngắt truyền audio. Kiểm tra lại tác vụ để tải file hoặc dùng trình duyệt.',504) from None
    except OSError as exc:
        if exc.errno in (errno.EACCES,errno.ENOSPC,errno.EROFS,getattr(errno,'EDQUOT',-1)):
            raise api.AudioError('[AUDIO_DISK] Không lưu được file audio. Kiểm tra quyền ghi và dung lượng thư mục ứng dụng.',500) from None
        raise api.AudioError('[AUDIO_IO] Lỗi đọc/ghi khi tải audio. Kiểm tra mạng và thư mục lưu, hoặc dùng trình duyệt.',502) from None


def media_format(path):
    with path.open('rb') as source:
        head=source.read(64)
    if head.startswith(b'ID3') or (len(head)>1 and head[0]==255 and head[1]&224==224):
        return 'mp3'
    if head.startswith(b'RIFF') and head[8:12]==b'WAVE':
        return 'wav'
    if head.startswith(b'fLaC'):
        return 'flac'
    if head.startswith(b'OggS'):
        return 'ogg'
    if head[4:8]==b'ftyp':
        return 'mov'
    raise api.AudioError('[AUDIO_FORMAT] Link trả dữ liệu không phải MP3/WAV/FLAC/Ogg/M4A, có thể là trang HTML báo lỗi. Mở audio gốc bằng trình duyệt hoặc nhập MP3 thủ công.')


def info(path):
    try:
        result=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type','-of','json',str(path)],capture_output=True,text=True,check=True,timeout=25)
        data=json.loads(result.stdout)
        duration=float(data['format']['duration'])
        if not math.isfinite(duration) or duration<=0 or not any(s.get('codec_type')=='audio' for s in data['streams']):
            raise ValueError()
        return dict(duration=round(duration,3),bytes=path.stat().st_size)
    except (subprocess.SubprocessError,OSError,ValueError,KeyError,TypeError):
        raise api.AudioError('Không xác minh được file âm thanh. Kiểm tra tác vụ rồi tải lại.') from None


def cache(raw,directory):
    task=api.task_id(raw)
    aid=asset_id(task)
    directory=Path(directory)
    directory.mkdir(exist_ok=True)
    with _MUTEX:
        lock=_LOCKS.setdefault(aid,threading.Lock())
    with lock:
        target=directory/(aid+'.mp3')
        if target.is_file():
            try:
                metadata=info(target)
                record=asset_store.write(directory,aid,**metadata,source='ai33',task_id=task)
                return asset_store.public(record)
            except api.AudioError:
                target.unlink(missing_ok=True)
        detail=api.get_task(raw)
        if detail['status']!='done' or not detail['audio_url']:
            raise api.AudioError('Tác vụ chưa có audio hoàn tất để tải. Tiếp tục kiểm tra tiến độ.',409)
        source=directory/(aid+'.download')
        encoded=directory/(aid+'.encoding.mp3')
        try:
            download(detail['audio_url'],source)
            fmt=media_format(source)
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y',
                            '-protocol_whitelist','file,pipe','-f',fmt,'-i',str(source),
                            '-map','0:a:0','-vn','-c:a','libmp3lame','-b:a','192k',str(encoded)],
                           capture_output=True,check=True,timeout=180)
            metadata=info(encoded)
            encoded.replace(target)
            old=asset_store.read(directory,aid)
            record=asset_store.write(directory,aid,**metadata,source='ai33',task_id=task,name=detail.get('name') or old.get('name') or task)
            return asset_store.public(record)
        except (subprocess.SubprocessError,OSError):
            raise api.AudioError('Không chuyển được audio sang MP3. Cần FFmpeg có libmp3lame; không cần tạo lại tác vụ.') from None
        finally:
            source.unlink(missing_ok=True)
            encoded.unlink(missing_ok=True)


def import_audio(source,directory,name):
    directory=Path(directory);directory.mkdir(exist_ok=True)
    aid=uuid.uuid4().hex;encoded=directory/(aid+'.encoding.mp3');target=directory/(aid+'.mp3')
    try:
        fmt=media_format(Path(source))
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y','-protocol_whitelist','file,pipe',
                        '-f',fmt,'-i',str(source),'-map','0:a:0','-vn','-c:a','libmp3lame','-b:a','192k',str(encoded)],
                       capture_output=True,check=True,timeout=300)
        metadata=info(encoded);encoded.replace(target)
        return asset_store.public(asset_store.write(directory,aid,name=asset_store.clean_name(name),source='upload',**metadata))
    except (subprocess.SubprocessError,OSError):
        raise api.AudioError('Không đọc được audio nhập. Dùng MP3/WAV/M4A/FLAC/Ogg hợp lệ và FFmpeg có libmp3lame.') from None
    finally:encoded.unlink(missing_ok=True)


def subtitles(raw):
    """Fetch the SRT transcript of a finished task (with_transcript=true) as text; never cached with keys."""
    detail=api.get_task(raw)
    if detail['status']!='done' or not detail.get('srt_url'):
        raise api.AudioError('Tác vụ này chưa có phụ đề. Bật "Xuất kèm phụ đề" khi tạo audio.',409)
    with tempfile.TemporaryDirectory() as folder:
        target=Path(folder)/'subtitles.srt'
        download(detail['srt_url'],target)
        if target.stat().st_size>2*1024*1024:raise api.AudioError('File phụ đề quá lớn.')
        text=target.read_bytes().decode('utf-8-sig','replace')
    if '-->' not in text:raise api.AudioError('Link phụ đề không trả về file SRT hợp lệ.')
    return dict(task_id=detail['task_id'],srt=text,name=detail.get('name') or detail['task_id'])
