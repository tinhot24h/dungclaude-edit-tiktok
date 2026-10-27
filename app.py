"""Local TikTok review video composer. Python 3.11+, FFmpeg, no pip packages."""
import base64
import json
import os
import re
import subprocess
import threading
import struct
import shutil
import unicodedata
import uuid
import time
from urllib.parse import unquote,quote
import asset_store
import media_engine
import media_preview
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from design import settings, layout, artwork, frame_box, video_box, artwork_layers
from fonts import FONTS
import ai_translate
import ai33_audio
import audio_files

ROOT = Path(__file__).resolve().parent
DATA = ROOT / '.local'
DATA.mkdir(exist_ok=True)
FRAMES = DATA / 'frames'
FRAMES.mkdir(exist_ok=True)
AUDIO = DATA / 'audio'
AUDIO.mkdir(exist_ok=True)
JOBS = {}
CANCELS = {}
LOCK = threading.Lock()
RENDER_LOCK = threading.Lock()
AI_SLOTS = threading.BoundedSemaphore(2)
AUDIO_SLOTS = threading.BoundedSemaphore(3)


def probe(path):
    data=media_engine.probe(path)
    if not data['has_video'] or data['duration']>1800:raise ValueError('Chọn video có hình ảnh, tối đa 30 phút.')
    return data


def validate_options(opts,strict=True):
    opts = settings(opts)
    for field, limit in [('title', 160), ('body', 600)]:
        value = opts.get(field)
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError(f'Nội dung {field} không hợp lệ (tối đa {limit} ký tự).')
        opts[field] = unicodedata.normalize('NFC', '\n'.join(' '.join(line.split()) for line in value.splitlines()))
    if opts['frame_style'] == 'custom' and not (FRAMES / (opts['frame_id']+'.png')).is_file():
        raise ValueError('Khung PNG không còn trong ứng dụng này. Hãy tải lại khung.')
    layout(opts,strict=strict)
    return opts


def compose(folder,options):
    folder=Path(folder)
    video=probe(folder/'source')
    aid=options.get('audio_asset_id','')
    audio_path=None;audio=None
    if aid:
        if not isinstance(aid,str) or not re.fullmatch('[a-f0-9]{32}',aid) or not (AUDIO/(aid+'.mp3')).is_file():raise ValueError('MP3 không còn trong thư viện. Hãy nhập hoặc tải lại audio.')
        audio_path=AUDIO/(aid+'.mp3');audio=media_engine.probe(audio_path)
    frame=FRAMES/(options.get('frame_id','')+'.png') if options['frame_style']=='custom' else None
    return media_engine.build(folder,options,folder/'source',video,audio_path,audio,frame)


def render(job_id,command,plan,name,cancel=None):
    cancel=cancel or threading.Event()
    folder=DATA/job_id;process=None;acquired=False
    result={'state':'error','error':'Xuất video bị gián đoạn.','name':name}
    try:
        while not cancel.is_set():
            acquired=RENDER_LOCK.acquire(timeout=.1)
            if acquired:break
        if cancel.is_set():return
        with LOCK:JOBS[job_id]={'state':'rendering','progress':0,'name':name,'plan':plan}
        progress=folder/'progress.txt';progress.unlink(missing_ok=True)
        with (folder/'render-error.log').open('wb') as err:
            process=subprocess.Popen(command,cwd=folder,stdout=subprocess.DEVNULL,stderr=err)
            deadline=time.monotonic()+7200
            while process.poll() is None:
                if cancel.wait(.15):
                    process.terminate()
                    try:process.wait(timeout=3)
                    except subprocess.TimeoutExpired:process.kill();process.wait()
                    break
                if time.monotonic()>deadline:
                    process.kill();process.wait();raise TimeoutError('Quá 2 giờ xử lý. Giảm thời lượng/độ phân giải.')
                try:
                    values=re.findall(r'out_time_us=(\d+)',progress.read_text(errors='replace')[-10000:])
                    percent=min(99,round(int(values[-1])/1000000/plan['duration']*100)) if values else 0
                    with LOCK:JOBS[job_id]['progress']=percent
                except OSError:pass
            if cancel.is_set():return
            if process.returncode:raise ValueError('FFmpeg xuất lỗi. Kiểm tra media và thông số, hoặc giảm độ phân giải.')
        actual=media_engine.probe(folder/'review.mp4')
        if (actual['width'],actual['height'])!=(plan['width'],plan['height']):raise ValueError('Kích thước xuất không đúng yêu cầu.')
        result={'state':'done','progress':100,'url':f'/download/{job_id}','name':name,'plan':plan,'duration':actual['duration']}
    except (subprocess.SubprocessError,OSError,ValueError,TimeoutError) as exc:
        result={'state':'error','error':str(exc),'name':name}
    finally:
        if process is not None and process.poll() is None:process.kill();process.wait()
        with LOCK:
            if cancel.is_set():
                (folder/'review.mp4').unlink(missing_ok=True)
                result={'state':'cancelled','name':name,'progress':0}
            JOBS[job_id]=result
            CANCELS.pop(job_id,None)
        if acquired:RENDER_LOCK.release()


class Handler(BaseHTTPRequestHandler):
    def respond(self, code, content, mime='application/json; charset=utf-8'):
        if not isinstance(content, bytes):
            content = json.dumps(content, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(content)

    def allowed(self):
        port = self.server.server_port
        hosts = (f'127.0.0.1:{port}',f'localhost:{port}')
        origin = self.headers.get('Origin')
        if self.headers.get('Host') not in hosts or (origin and origin not in ('http://'+host for host in hosts)):
            self.respond(403, {'error':'Chỉ chấp nhận truy cập từ ứng dụng cục bộ.'})
            return False
        return True

    def serve_audio(self,path,attachment=False,mime='audio/mpeg',filename='review-voice.mp3'):
        size=path.stat().st_size
        start,end=0,size-1
        range_header=self.headers.get('Range')
        if range_header:
            match=re.fullmatch(r'bytes=(\d*)-(\d*)',range_header)
            valid=bool(match and (match[1] or match[2]))
            if valid:
                if match[1]:
                    start=int(match[1])
                    end=min(size-1,int(match[2])) if match[2] else size-1
                else:
                    valid=int(match[2])>0
                    start=max(0,size-int(match[2]))
                valid=valid and start<=end and start<size
            if not valid:
                self.send_response(416)
                self.send_header('Content-Range',f'bytes */{size}')
                self.send_header('Content-Length','0')
                self.end_headers()
                return
        self.send_response(206 if range_header else 200)
        self.send_header('Content-Type',mime)
        self.send_header('Accept-Ranges','bytes')
        self.send_header('Content-Length',str(end-start+1))
        self.send_header('Content-Disposition',('attachment' if attachment else 'inline')+"; filename=\"media\"; filename*=UTF-8''"+quote(filename))
        self.send_header('X-Content-Type-Options','nosniff')
        if range_header:
            self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.end_headers()
        remaining=end-start+1
        try:
            with path.open('rb') as source:
                source.seek(start)
                while remaining:
                    chunk=source.read(min(remaining,256*1024))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining-=len(chunk)
        except (BrokenPipeError,ConnectionResetError):
            pass

    def do_GET(self):
        if not self.allowed():
            return
        path = urlparse(self.path).path
        if path == '/':
            return self.respond(200, (ROOT / 'index.html').read_bytes(), 'text/html; charset=utf-8')
        if path in ('/studio.css','/studio.js','/ai_ui.js','/audio_ui.js','/editor_ui.js','/timeline_ui.js'):
            mime = 'text/css' if path.endswith('.css') else 'text/javascript'
            return self.respond(200, (ROOT/path.lstrip('/')).read_bytes(), mime+'; charset=utf-8')
        if path in ('/assets/'+font[0] for font in FONTS.values()):
            return self.respond(200, (ROOT / path.lstrip('/')).read_bytes(), 'font/ttf')
        match = re.fullmatch(r'/frames/([a-f0-9]{32})', path)
        if match and (FRAMES / (match[1]+'.png')).is_file():
            return self.respond(200, (FRAMES / (match[1]+'.png')).read_bytes(), 'image/png')
        if path == '/audio/assets':
            return self.respond(200,{'assets':asset_store.assets(AUDIO)})
        analysis=re.fullmatch(r'/media/analysis/(video|audio)/([a-f0-9]{32})',path)
        if analysis:
            kind,aid=analysis.groups()
            source=DATA/aid/'source' if kind=='video' else AUDIO/(aid+'.mp3')
            if not source.is_file():return self.respond(404,{'error':'Nguồn không còn trong thư mục này.'})
            try:return self.respond(200,media_preview.analyze(source,DATA/'previews'/(kind+'-'+aid+'.json'),kind))
            except (OSError,ValueError,subprocess.SubprocessError):return self.respond(400,{'error':'Chưa tạo được hình/sóng âm. Vẫn có thể cắt bằng số.'})
        video_match=re.fullmatch(r'/media/video/([a-f0-9]{32})(/info)?',path)
        if video_match and (DATA/video_match[1]/'source').is_file():
            if video_match[2]:
                try:
                    data=json.loads((DATA/video_match[1]/'source.json').read_text(encoding='utf-8'))
                    return self.respond(200,data)
                except (OSError,ValueError):return self.respond(404,{'error':'Không có thông tin nguồn.'})
            return self.serve_audio(DATA/video_match[1]/'source',False,'video/mp4','source.mp4')
        if path == '/audio-config':
            return self.respond(200, {'configured':ai33_audio.configured()})
        audio_match=re.fullmatch(r'/audio/file/([a-f0-9]{32})',path)
        if audio_match and (AUDIO / (audio_match[1]+'.mp3')).is_file():
            record=asset_store.read(AUDIO,audio_match[1]);name=record.get('name','review-voice')
            name=re.sub(r'\.(mp3|wav|m4a|ogg|flac)$','',name,flags=re.I)+'.mp3'
            return self.serve_audio(AUDIO / (audio_match[1]+'.mp3'), 'download=1' in urlparse(self.path).query.split('&'),filename=name)
        if path == '/ai-status':
            return self.respond(200, {'configured':ai_translate.configured(),'model':ai_translate.default_model(),
                                     'providers':{name:dict(configured=ai_translate.configured(name),model=ai_translate.default_model(name))
                                                  for name in ('openai','gemini')}})
        if path == '/health':
            return self.respond(200, {'status': 'ok'})
        match = re.fullmatch(r'/(jobs|download)/([a-f0-9]{32})', path)
        if match:
            kind, key = match.groups()
            with LOCK:
                job = JOBS.get(key)
            if kind == 'jobs' and job:
                return self.respond(200, job)
            output = DATA / key / 'review.mp4'
            if kind == 'download' and job and job['state'] == 'done' and output.is_file():
                self.send_response(200)
                self.send_header('Content-Type', 'video/mp4')
                self.send_header('Content-Disposition', "attachment; filename=\"review.mp4\"; filename*=UTF-8''"+quote(JOBS.get(key,{}).get('name','review')+'.mp4'))
                self.send_header('Content-Length', str(output.stat().st_size))
                self.end_headers()
                with output.open('rb') as source:
                    while chunk := source.read(1024 * 1024):
                        self.wfile.write(chunk)
                return
        self.respond(404, {'error': 'Không tìm thấy.'})

    def do_POST(self):
        if not self.allowed():
            return
        path = urlparse(self.path).path
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if path=='/audio/upload':
                if not 0<size<=100*1024*1024:raise ValueError('MP3 nhập tối đa 100 MB.')
                original=asset_store.clean_name(unquote(self.headers.get('X-Filename','audio.mp3')))
                temp=AUDIO/(uuid.uuid4().hex+'.input')
                try:
                    with temp.open('wb') as out:
                        remaining=size
                        while remaining:
                            chunk=self.rfile.read(min(1024*1024,remaining))
                            if not chunk:raise ValueError('Tải audio bị gián đoạn.')
                            out.write(chunk);remaining-=len(chunk)
                    return self.respond(200,audio_files.import_audio(temp,AUDIO,original))
                finally:temp.unlink(missing_ok=True)
            if path in ('/audio/voices','/audio/create','/audio/task','/audio/history','/audio/credits','/audio/cache'):
                if not 0 < size <= (4*1024*1024 if path=='/audio/create' else 32768):
                    raise ValueError('Yêu cầu audio quá lớn hoặc trống.')
                raw=json.loads(self.rfile.read(size))
                if not isinstance(raw,dict):
                    raise ValueError('Yêu cầu audio không hợp lệ.')
                if not AUDIO_SLOTS.acquire(blocking=False):
                    return self.respond(429, {'error':'Đang xử lý các yêu cầu âm thanh khác. Hãy chờ, không tạo lại tác vụ.'})
                try:
                    if path=='/audio/voices':
                        result=ai33_audio.voice_library(raw)
                    elif path=='/audio/create':
                        result=ai33_audio.create_tts(raw)
                        aid=audio_files.asset_id(result['task_id'])
                        record=asset_store.write(AUDIO,aid,name=raw.get('file_name') or result['task_id'],source='ai33',task_id=result['task_id'],voice_id=raw.get('voice_id',''))
                        result['name']=record['name']
                    elif path=='/audio/history':
                        result=ai33_audio.list_tasks(raw)
                        for task in result['tasks']:
                            record=asset_store.read(AUDIO,audio_files.asset_id(task['task_id']))
                            task['name']=task.get('name') or record.get('name') or task['task_id']
                    elif path=='/audio/credits':
                        result=ai33_audio.credits(raw)
                    elif path=='/audio/cache':
                        result=audio_files.cache(raw,AUDIO)
                    else:
                        detail=ai33_audio.get_task(raw)
                        result={key:value for key,value in detail.items() if key!='audio_url'}
                        result['audio_available']=bool(detail['audio_url'])
                        result['remote_audio_url']=detail['audio_url']
                        record=asset_store.read(AUDIO,audio_files.asset_id(detail['task_id']))
                        result['name']=detail.get('name') or record.get('name') or detail['task_id']
                        asset_store.write(AUDIO,audio_files.asset_id(detail['task_id']),name=result['name'],source='ai33',task_id=detail['task_id'])
                finally:
                    AUDIO_SLOTS.release()
                return self.respond(200,result)
            if path in ('/translation-prompt','/translation-import'):
                if not 0 < size <= 196608:
                    raise ValueError('Yêu cầu quá lớn.')
                raw = json.loads(self.rfile.read(size))
                result = {'prompt':ai_translate.manual_prompt(raw)} if path.endswith('prompt') else ai_translate.import_manual(raw)
                return self.respond(200,result)
            if path == '/translate':
                if not 0 < size <= 65536:
                    raise ValueError('Yêu cầu dịch quá lớn.')
                raw = json.loads(self.rfile.read(size))
                if not AI_SLOTS.acquire(blocking=False):
                    return self.respond(429, {'error':'Đang xử lý các bản dịch khác. Hãy chờ rồi thử lại.'})
                try:
                    result = ai_translate.translate(raw)
                finally:
                    AI_SLOTS.release()
                return self.respond(200,result)
            if path == '/frame-upload':
                if not 0 < size <= 5*1024*1024:
                    return self.respond(413, {'error': 'Khung PNG tối đa 5 MB.'})
                data = self.rfile.read(size)
                if len(data) != size or data[:8] != b'\x89PNG\r\n\x1a\n' or data[12:16] != b'IHDR' or len(data)<33:
                    raise ValueError('Tệp không phải PNG hợp lệ.')
                width, height = struct.unpack('!II',data[16:24])
                if not 0 < width <= 4096 or not 0 < height <= 4096 or width*height>8000000:
                    raise ValueError('PNG tối đa 4096 px mỗi cạnh và 8 triệu điểm ảnh.')
                key = uuid.uuid4().hex
                source, target = FRAMES/(key+'-upload.png'), FRAMES/(key+'.png')
                source.write_bytes(data)
                try:
                    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y',
                                    '-f','image2','-c:v','png','-i',str(source),'-frames:v','1',
                                    '-vf','format=rgba',str(target)],capture_output=True,check=True,timeout=25)
                except subprocess.SubprocessError:
                    target.unlink(missing_ok=True)
                    raise ValueError('Không đọc được PNG. Hãy xuất lại dưới dạng PNG tĩnh.')
                finally:
                    source.unlink(missing_ok=True)
                return self.respond(200, {'id': key,'url':'/frames/'+key,'width':width,'height':height})
            if path == '/upload':
                if not 0 < size <= 500 * 1024 * 1024:
                    return self.respond(413, {'error': 'Chọn video tối đa 500 MB.'})
                key = uuid.uuid4().hex
                folder = DATA / key
                folder.mkdir()
                remaining = size
                with (folder / 'source').open('wb') as output:
                    while remaining:
                        chunk = self.rfile.read(min(1024 * 1024, remaining))
                        if not chunk:
                            raise ValueError('Tải lên bị gián đoạn.')
                        output.write(chunk)
                        remaining -= len(chunk)
                metadata=probe(folder/'source')
                name=asset_store.clean_name(unquote(self.headers.get('X-Filename','video.mp4')))
                data=dict(id=key,name=name,url='/media/video/'+key,**metadata)
                (folder/'source.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
                return self.respond(200,data)
            if path == '/design':
                if not 0 < size <= 8192:
                    raise ValueError('Yêu cầu không hợp lệ.')
                opts = validate_options(json.loads(self.rfile.read(size)),strict=False)
                custom = None
                if opts['frame_style'] == 'custom':
                    custom = dict(url='/frames/'+opts['frame_id'],**frame_box(opts),opacity=opts['frame_opacity']/100)
                if opts.get('preview_layers'):
                    bg,frame=artwork_layers(opts)
                else:bg,frame=artwork(opts),None
                image=lambda data:'data:image/png;base64,'+base64.b64encode(data).decode()
                return self.respond(200,{'image':image(bg),'frame_image':image(frame) if frame else None,
                                         'text':layout(opts,strict=False),'custom':custom,'frame':frame_box(opts),'video':video_box(opts)})
            cancel_match=re.fullmatch(r'/jobs/([a-f0-9]{32})/cancel',path)
            if cancel_match:
                key=cancel_match[1]
                with LOCK:
                    job=JOBS.get(key)
                    if not job:return self.respond(404,{'error':'Không tìm thấy tác vụ xuất.'})
                    event=CANCELS.get(key)
                    if event and job['state'] in ('queued','rendering','cancelling'):
                        event.set();job['state']='cancelling'
                    result=dict(job)
                return self.respond(200,result)
            if path == '/render':
                if not 0 < size <= 8192:
                    raise ValueError('Yêu cầu không hợp lệ.')
                opts = validate_options(json.loads(self.rfile.read(size)))
                key = opts.get('id', '')
                if not isinstance(key, str) or not re.fullmatch('[a-f0-9]{32}', key):
                    raise ValueError('Hãy tải clip lên trước.')
                folder = DATA / key
                if not (folder / 'source').is_file():
                    raise ValueError('Không tìm thấy clip.')
                with LOCK:
                    if JOBS.get(key, {}).get('state') in ('queued', 'rendering', 'cancelling'):
                        return self.respond(409, {'error': 'Clip đang được xử lý.'})
                    JOBS[key] = {'state': 'queued'}
                try:
                    command,plan=compose(folder,opts)
                except ValueError:
                    with LOCK:
                        JOBS.pop(key, None)
                    raise
                name=asset_store.clean_name(opts.get('project_name'),'review-video').removesuffix('.mp4')
                cancel=threading.Event()
                with LOCK:CANCELS[key]=cancel
                threading.Thread(target=render,args=(key,command,plan,name,cancel),daemon=True).start()
                return self.respond(202, {'id': key})
            self.respond(404, {'error': 'Không tìm thấy.'})
        except ai33_audio.AudioError as error:
            self.respond(error.status, {'error':str(error)})
        except ai_translate.AIError as error:
            self.respond(error.status, {'error':str(error)})
        except ValueError as error:
            self.respond(400, {'error': str(error)})
        except (KeyError, TypeError, subprocess.SubprocessError):
            self.respond(400, {'error': 'Dữ liệu không hợp lệ. Dùng clip video tối đa 30 phút.'})


if __name__ == '__main__':
    address = ('127.0.0.1', int(os.environ.get('PORT', '8000')))
    print(f'Review Studio running on port {address[1]}', flush=True)
    ThreadingHTTPServer(address, Handler).serve_forever()
