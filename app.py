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
from urllib.parse import urlparse, parse_qs
from design import settings, layout, artwork, frame_box, video_box, artwork_layers, TEXT_LIMITS
from fonts import FONTS
import ai_translate
import ai33_audio
import audio_files
import library_store
import output_folder
import update
import dubbing
import secrets_store

ROOT = Path(__file__).resolve().parent
DATA = ROOT / '.local'
DATA.mkdir(exist_ok=True)
FRAMES = DATA / 'frames'
FRAMES.mkdir(exist_ok=True)
AUDIO = DATA / 'audio'
AUDIO.mkdir(exist_ok=True)
IMAGES = DATA / 'images'
IMAGES.mkdir(exist_ok=True)
SETTINGS = DATA / 'settings.json'
JOBS = {}
CANCELS = {}
LOCK = threading.Lock()
RENDER_LOCK = threading.Lock()
AUDIO_SLOTS = threading.BoundedSemaphore(3)
ACTIVE = ('queued','rendering','cancelling')
PROJECT = re.compile('[a-f0-9]{32}')
VERSION = (ROOT/'VERSION').read_text(encoding='utf-8').strip()
RESTART_CODE = 75
DUB = dubbing.Store(DATA, SETTINGS, DATA, AUDIO, media_engine.encoder_args)
DUB.frames_dir, DUB.images_dir = FRAMES, IMAGES   # custom frames and logo layers of the design templates
try:
    library_store.merge_build_presets(DATA/'library')   # one tab since 0.22: build templates join the dub presets
except (OSError, ValueError):
    pass
secrets_store.forget_removed()   # the Gemini key of the removed "Dịch & biên tập AI" page


def keep_days():
    try:return max(0,int(os.environ.get('REVIEW_KEEP_DAYS','30')))
    except ValueError:return 30


VIDEO_EXT=('.mp4','.mov','.m4v','.mkv','.webm','.avi','.flv','.ts')
AUDIO_EXT=('.mp3','.wav','.m4a','.aac','.flac','.ogg','.opus','.wma')
IMAGE_EXT=('.png','.jpg','.jpeg','.webp','.gif')
MEDIA_EXT=VIDEO_EXT+AUDIO_EXT+IMAGE_EXT
MIME={'.mp4':'video/mp4','.m4v':'video/mp4','.mov':'video/quicktime','.mkv':'video/x-matroska','.webm':'video/webm','.avi':'video/x-msvideo','.flv':'video/x-flv','.ts':'video/mp2t',
      '.mp3':'audio/mpeg','.wav':'audio/wav','.m4a':'audio/mp4','.aac':'audio/aac','.flac':'audio/flac','.ogg':'audio/ogg','.opus':'audio/ogg','.wma':'audio/x-ms-wma',
      '.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp','.gif':'image/gif','.srt':'application/x-subrip'}
# every "add file" endpoint also accepts X-Local-Path: the file is read where it is on this computer, nothing uploaded
LOCAL_UPLOADS={'/upload':VIDEO_EXT,'/audio/upload':AUDIO_EXT+VIDEO_EXT,'/frame-upload':('.png',),'/image-upload':IMAGE_EXT,
               '/dub/images/upload':IMAGE_EXT,'/overlays/upload':VIDEO_EXT+IMAGE_EXT}
PICK_TYPES={'video':[('Video','*.mp4 *.mov *.m4v *.mkv *.webm *.avi *.flv *.ts')],'audio':[('Âm thanh','*.mp3 *.wav *.m4a *.aac *.flac *.ogg *.opus')],
            'image':[('Ảnh','*.png *.jpg *.jpeg *.webp *.gif')],'srt':[('Phụ đề SRT','*.srt')],'json':[('JSON','*.json')]}


def link_or_copy(src,target):
    """Bring a file from this computer into the app without uploading: a hard link is instant and takes no extra
    space (same drive, NTFS/ext4); on another drive the file is copied disk to disk. The original is never changed
    and deleting it from the app only removes the link."""
    try:
        os.link(src,target);return 'link'
    except OSError:
        shutil.copyfile(src,target);return 'copy'


def local_file(raw,kinds):
    path=raw.get('path') if isinstance(raw,dict) else None
    if not isinstance(path,str) or not 0<len(path)<=1000:raise ValueError('Đường dẫn file không hợp lệ.')
    src=Path(path)
    if not src.is_absolute() or not src.is_file() or src.suffix.lower() not in kinds:raise ValueError('Không đọc được file: '+src.name)
    return src


def scan_folder(raw,kinds):
    """Files of the given kinds in a folder chosen on this computer (sub-folders included), sorted by name."""
    folder=raw.get('folder') if isinstance(raw,dict) else None
    if not isinstance(folder,str) or not folder or not Path(folder).is_dir():raise ValueError('Thư mục không tồn tại.')
    out=[]
    for item in sorted(Path(folder).rglob('*'),key=lambda p:str(p).lower()):
        if item.is_file() and item.suffix.lower() in kinds and not item.name.startswith('.'):
            try:out.append(dict(path=str(item),name=item.name,size=item.stat().st_size))
            except OSError:continue
            if len(out)>=5000:break
    return out


def probe(path):
    data=media_engine.probe(path)
    if not data['has_video'] or data['duration']>media_engine.MAX_SECONDS:raise ValueError('Chọn video có hình ảnh, tối đa 30 phút.')
    return data


def save_job(job_id,job):
    """Persist a finished export so its download survives an app restart."""
    try:
        tmp=DATA/job_id/'job.json.tmp';tmp.write_text(json.dumps(job,ensure_ascii=False),encoding='utf-8');tmp.replace(DATA/job_id/'job.json')
    except OSError:pass


def load_job(job_id):
    with LOCK:job=JOBS.get(job_id)
    if job:return job
    try:job=json.loads((DATA/job_id/'job.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):return None
    return job if isinstance(job,dict) and job.get('state') in ('done','error','cancelled') else None


def folder_size(path):
    total=0
    for item in Path(path).rglob('*'):
        try:total+=item.stat().st_size if item.is_file() else 0
        except OSError:pass
    return total


def projects():
    return [item for item in DATA.iterdir() if item.is_dir() and PROJECT.fullmatch(item.name)]


def delete_project(key):
    with LOCK:
        if JOBS.get(key,{}).get('state') in ACTIVE:raise ValueError('Video đang xuất. Hủy xuất trước khi xóa.')
        JOBS.pop(key,None)
        shutil.rmtree(DATA/key)
    (DATA/'previews'/('video-'+key+'.json')).unlink(missing_ok=True)


def delete_audio(aid):
    if not PROJECT.fullmatch(aid) or not (AUDIO/(aid+'.mp3')).is_file():raise ValueError('MP3 không còn trong thư viện.')
    try:
        for suffix in ('.mp3','.json'):(AUDIO/(aid+suffix)).unlink(missing_ok=True)
    except OSError:raise ValueError('Không xóa được MP3. Có thể file đang được dùng để xuất video; thử lại sau.') from None
    (DATA/'previews'/('audio-'+aid+'.json')).unlink(missing_ok=True)


def videos():
    rows=[]
    for folder in projects():
        try:data=json.loads((folder/'source.json').read_text(encoding='utf-8'));stamp=(folder/'source').stat().st_mtime
        except (OSError,ValueError):continue
        if isinstance(data,dict) and data.get('id')==folder.name:rows.append({**data,'thumb':'/media/thumb/'+folder.name,'uploaded':stamp})
    return sorted(rows,key=lambda r:r['uploaded'],reverse=True)


def thumbnail(key):
    target=DATA/key/'thumb.jpg'
    if not target.is_file():
        duration=json.loads((DATA/key/'source.json').read_text(encoding='utf-8')).get('duration',0)
        subprocess.run(['ffmpeg','-v','error','-nostdin','-y','-ss',str(min(1,duration/3)),'-i',str(DATA/key/'source'),'-frames:v','1',
                        '-vf','scale=160:284:force_original_aspect_ratio=increase,crop=160:284','-q:v','5',str(target)],capture_output=True,check=True,timeout=20)
    return target.read_bytes()


IMAGE_KINDS={b'\x89PNG':('image2','png'),b'\xff\xd8\xff':('image2','mjpeg'),b'GIF8':('gif',None),b'RIFF':('image2','webp')}


def import_image(data,name):
    """Store an uploaded PNG/JPEG/WebP/GIF (first frame) as an RGBA PNG, at most 2048 px per side."""
    kind=next((v for k,v in IMAGE_KINDS.items() if data.startswith(k)),None)
    if not kind or (data.startswith(b'RIFF') and data[8:12]!=b'WEBP'):raise ValueError('Chọn ảnh PNG, JPG, WebP hoặc GIF.')
    key=uuid.uuid4().hex;source,target=IMAGES/(key+'.upload'),IMAGES/(key+'.png')
    source.write_bytes(data)
    try:
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y','-f',kind[0],*(['-c:v',kind[1]] if kind[1] else []),'-i',str(source),
                        '-frames:v','1','-vf',"scale='min(2048,iw)':'min(2048,ih)':force_original_aspect_ratio=decrease,format=rgba",str(target)],
                       capture_output=True,check=True,timeout=30)
        width,height=struct.unpack('!II',target.read_bytes()[16:24])
    except (subprocess.SubprocessError,OSError,struct.error):
        target.unlink(missing_ok=True)
        raise ValueError('Không đọc được ảnh. Hãy lưu lại dưới dạng PNG hoặc JPG.') from None
    finally:source.unlink(missing_ok=True)
    record=dict(id=key,name=asset_store.clean_name(name,'anh'),width=width,height=height,url='/images/'+key)
    (IMAGES/(key+'.json')).write_text(json.dumps(record,ensure_ascii=False),encoding='utf-8')
    return record


def images():
    rows=[]
    for path in IMAGES.glob('*.json'):
        try:record=json.loads(path.read_text(encoding='utf-8'))
        except (OSError,ValueError):continue
        if isinstance(record,dict) and record.get('id')==path.stem and PROJECT.fullmatch(path.stem) and path.with_suffix('.png').is_file():
            rows.append({**record,'uploaded':path.stat().st_mtime})
    return sorted(rows,key=lambda r:r['uploaded'],reverse=True)


def storage():
    folders=projects()
    return dict(projects=len(folders),project_bytes=sum(folder_size(f) for f in folders),
                audio_bytes=folder_size(AUDIO),frame_bytes=folder_size(FRAMES),keep_days=keep_days())


def cleanup(days):
    """Remove video projects idle for `days` and temp files left by a crash; never touches the MP3 library."""
    cutoff=time.time()-days*86400;removed=freed=0
    for folder in projects():
        try:
            last=max([folder.stat().st_mtime]+[item.stat().st_mtime for item in folder.iterdir()])
            if last>=cutoff:continue
            size=folder_size(folder);delete_project(folder.name)
            removed+=1;freed+=size
        except (OSError,ValueError):pass
    stale=time.time()-86400
    for pattern,directory in [('*.input',AUDIO),('*.download',AUDIO),('*.encoding.mp3',AUDIO),('*.json.tmp',AUDIO),('*-upload.png',FRAMES)]:
        for item in directory.glob(pattern):
            try:
                if item.stat().st_mtime<stale:item.unlink()
            except OSError:pass
    return dict(removed=removed,freed=freed,**storage())


def validate_options(opts,strict=True):
    opts = settings(opts)
    for field, limit in TEXT_LIMITS.items():
        value = opts.get(field, '')
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError(f'Nội dung {field} không hợp lệ (tối đa {limit} ký tự).')
        opts[field] = unicodedata.normalize('NFC', '\n'.join(' '.join(line.split()) for line in value.splitlines()))
    if opts['frame_style'] == 'custom' and not (FRAMES / (opts['frame_id']+'.png')).is_file():
        raise ValueError('Khung PNG không còn trong ứng dụng này. Hãy tải lại khung.')
    for image in opts['images']:
        if not (IMAGES/(image['id']+'.png')).is_file():raise ValueError('Ảnh của một lớp ảnh không còn trong ứng dụng. Hãy nhập lại ảnh.')
    layout(opts,strict=strict)
    return opts


def library_audio(aid,label):
    if not isinstance(aid,str) or not PROJECT.fullmatch(aid) or not (AUDIO/(aid+'.mp3')).is_file():raise ValueError(label+' không còn trong thư viện. Hãy nhập hoặc tải lại audio.')
    return AUDIO/(aid+'.mp3')


def compose(folder,options):
    """Build the FFmpeg command(s); a hardware encoder gets a libx264 fallback command."""
    folder=Path(folder)
    video=probe(folder/'source')
    audio_path=audio=music_path=music=None
    if options.get('audio_asset_id',''):
        audio_path=library_audio(options['audio_asset_id'],'MP3');audio=media_engine.probe(audio_path)
    if options.get('music_asset_id',''):
        music_path=library_audio(options['music_asset_id'],'Nhạc nền');music=media_engine.probe(music_path)
    frame=FRAMES/(options.get('frame_id','')+'.png') if options['frame_style']=='custom' else None
    command,plan=media_engine.build(folder,options,folder/'source',video,audio_path,audio,frame,music_path,music,IMAGES)
    fallback=None
    if plan['encoder']!='cpu':
        fallback,_=media_engine.build(folder,{**options,'encoder':'cpu'},folder/'source',video,audio_path,audio,frame,music_path,music,IMAGES)
    return command,plan,fallback


def render(job_id,command,plan,name,cancel=None,fallback=None):
    cancel=cancel or threading.Event()
    folder=DATA/job_id;process=None;acquired=False
    output=folder/plan.get('output','review.mp4');length=plan.get('output_duration',plan.get('duration',1)) or 1
    result={'state':'error','error':'Xuất video bị gián đoạn.','name':name}
    try:
        while not cancel.is_set():
            acquired=RENDER_LOCK.acquire(timeout=.1)
            if acquired:break
        if cancel.is_set():return
        started=time.time()
        with LOCK:JOBS[job_id]={'state':'rendering','progress':0,'name':name,'plan':plan,'eta':None,'encoder':plan.get('encoder','cpu')}
        progress=folder/'progress.txt'
        for attempt in [command]+([fallback] if fallback else []):
            progress.unlink(missing_ok=True)
            with (folder/'render-error.log').open('wb') as err:
                process=subprocess.Popen(attempt,cwd=folder,stdout=subprocess.DEVNULL,stderr=err)
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
                        percent=min(99,round(int(values[-1])/1000000/length*100)) if values else 0
                        elapsed=time.time()-started
                        with LOCK:JOBS[job_id].update(progress=percent,eta=round(elapsed*(100-percent)/percent) if percent>=3 else None)
                    except OSError:pass
            if cancel.is_set():return
            if not process.returncode:break
            if attempt is not fallback and fallback:
                # Hardware encoders fail on some drivers; finish the export on the CPU instead.
                with LOCK:JOBS[job_id].update(progress=0,eta=None,encoder='cpu',note='Card đồ họa không xuất được, chuyển sang CPU.')
                started=time.time();continue
            raise ValueError('FFmpeg xuất lỗi. Kiểm tra media và thông số, hoặc giảm độ phân giải.')
        actual=media_engine.probe(output)
        if (actual['width'],actual['height'])!=(plan['width'],plan['height']):raise ValueError('Kích thước xuất không đúng yêu cầu.')
        with LOCK:encoder=JOBS[job_id].get('encoder','cpu')
        result={'state':'done','progress':100,'url':f'/download/{job_id}','name':name,'plan':plan,'duration':actual['duration'],
                'file':output.name,'preview':output.name=='preview.mp4','encoder':encoder,'seconds':round(time.time()-started,1)}
        if not result['preview'] and output_folder.load(SETTINGS)['auto_save']:
            try:result['saved_path']=str(output_folder.deliver(SETTINGS,output,name))
            except ValueError as exc:result['save_error']=str(exc)
    except (subprocess.SubprocessError,OSError,ValueError,TimeoutError) as exc:
        result={'state':'error','error':str(exc),'name':name}
    finally:
        if process is not None and process.poll() is None:process.kill();process.wait()
        with LOCK:
            if cancel.is_set():
                output.unlink(missing_ok=True)
                result={'state':'cancelled','name':name,'progress':0}
            JOBS[job_id]=result
            CANCELS.pop(job_id,None)
        save_job(job_id,result)
        if acquired:RENDER_LOCK.release()


class Handler(BaseHTTPRequestHandler):
    def respond(self, code, content, mime='application/json; charset=utf-8'):
        if not isinstance(content, bytes):
            content = json.dumps(content, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        # pages and scripts are always re-checked, so an update is visible without clearing the browser cache
        self.send_header('Cache-Control', 'no-cache')
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
        if path in ('/studio.css','/studio.js','/local_files.js','/design_tab.js','/audio_ui.js','/editor_ui.js','/timeline_ui.js','/history_ui.js','/workspace_ui.js','/clip_ui.js','/studio_shell.js','/media_bin.js','/image_ui.js','/export_ui.js','/style_ui.js','/update_ui.js','/dub_ui.js','/layout_ui.js','/key_ui.js','/batch_ui.js'):
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
        if path == '/dub/template-defaults':
            return self.respond(200, {'rules':ai_translate.DEFAULT_RULES,'fixed':dubbing.DUB_GUARD+'\n\n'+ai_translate.STRICT,'max':ai_translate.MAX_RULES})
        if path == '/health':
            return self.respond(200, {'status': 'ok','version':VERSION})
        library=re.fullmatch(r'/library/(projects|templates|styles|presets|dubpresets|buildpresets)(?:/([a-f0-9]{32}))?',path)
        if library:
            try:
                if library[2]:return self.respond(200,library_store.read(DATA/'library',library[1],library[2]))
                return self.respond(200,{'items':library_store.items(DATA/'library',library[1])})
            except ValueError as error:return self.respond(404,{'error':str(error)})
        if path == '/media/videos':
            return self.respond(200,{'videos':videos()})
        thumb=re.fullmatch(r'/media/thumb/([a-f0-9]{32})',path)
        if thumb and (DATA/thumb[1]/'source').is_file():
            try:return self.respond(200,thumbnail(thumb[1]),'image/jpeg')
            except (OSError,ValueError,subprocess.SubprocessError):return self.respond(404,{'error':'Chưa tạo được ảnh nhỏ.'})
        image_match=re.fullmatch(r'/images/([a-f0-9]{32})',path)
        if image_match and (IMAGES/(image_match[1]+'.png')).is_file():
            return self.respond(200,(IMAGES/(image_match[1]+'.png')).read_bytes(),'image/png')
        if path == '/images':
            return self.respond(200,{'images':images()})
        if path == '/secrets':
            return self.respond(200,secrets_store.status())
        if path == '/app/info':
            return self.respond(200,{'version':VERSION,'root':str(ROOT)})
        if path == '/local/file':
            # previews of files picked on this computer; only this app's own pages may load them
            if self.headers.get('Sec-Fetch-Site') not in (None,'same-origin','none'):return self.respond(403,{'error':'Không cho phép.'})
            try:src=local_file({'path':parse_qs(urlparse(self.path).query).get('path',[''])[0]},MEDIA_EXT)
            except ValueError as exc:return self.respond(404,{'error':str(exc)})
            return self.serve_audio(src,False,MIME[src.suffix.lower()],src.name)
        if path == '/dub/images':
            return self.respond(200,{'images':DUB.images()})
        dimg=re.fullmatch(r'/dub/images/([a-f0-9]{32})/file',path)
        if dimg:
            item=DUB.image(dimg[1])
            if not item:return self.respond(404,{'error':'Không tìm thấy ảnh.'})
            mime={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp'}[Path(item['file']).suffix.lower()]
            return self.respond(200,(DUB.image_dir/item['file']).read_bytes(),mime)
        if path == '/overlays':
            return self.respond(200,{'overlays':DUB.overlays()})
        ov=re.fullmatch(r'/overlays/([a-f0-9]{32})/(file|thumb|preview)',path)
        if ov:
            item=DUB.overlay(ov[1])
            if not item:return self.respond(404,{'error':'Không tìm thấy overlay.'})
            if ov[2]=='thumb':
                thumb=DUB.overlay_thumb(item)
                return self.respond(200,thumb.read_bytes(),'image/png' if thumb.suffix=='.png' else 'image/jpeg') if thumb else self.respond(404,{'error':'Chưa có ảnh nhỏ.'})
            if ov[2]=='preview':
                shown=DUB.overlay_preview(item)
                if shown.name.endswith('.preview.webm'):return self.serve_audio(shown,False,'video/webm',item['name'])
            ext=Path(item['file']).suffix.lower()
            mime={'.mp4':'video/mp4','.m4v':'video/mp4','.mov':'video/quicktime','.webm':'video/webm','.mkv':'video/x-matroska','.gif':'image/gif','.png':'image/png','.webp':'image/webp','.jpg':'image/jpeg','.jpeg':'image/jpeg'}[ext]
            return self.serve_audio(DATA/'overlays'/item['file'],False,mime,item['name'])
        if path == '/dub/jobs':
            return self.respond(200,{'jobs':DUB.jobs()})
        if path == '/dub/queue':
            return self.respond(200,DUB.queue_info())
        if path == '/dub/demucs':
            return self.respond(200,dubbing.demucs_status('refresh' in parse_qs(urlparse(self.path).query)))
        if path == '/dub/capabilities':
            return self.respond(200,{'demucs':bool(dubbing.demucs_command()),'openai':bool(dubbing.openai_key({})),'ai33':bool(dubbing.ai33_key({})),
                                     'defaults':dubbing.DEFAULTS,'models':dubbing.MODELS,'whisper_per_minute':dubbing.WHISPER_PER_MINUTE,'pronouns':dubbing.PRONOUNS,'styles':ai_translate.STYLE_LABELS})
        sample=re.fullmatch(r'/dub/sample/([a-f0-9]{24})\.mp3',path)
        if sample:
            try:return self.serve_audio(DUB.sample_file(sample[1]))
            except dubbing.DubError as exc:return self.respond(exc.status,{'error':str(exc)})
        dub=re.fullmatch(r'/dub/([a-f0-9]{32})(?:/(download|srt/vi|srt/zh))?',path)
        if dub:
            try:job=DUB.load(dub[1])
            except dubbing.DubError as exc:return self.respond(exc.status,{'error':str(exc)})
            if not dub[2]:return self.respond(200,job)
            folder=DATA/'dub'/dub[1]
            if dub[2]=='download':
                target=folder/'dubbed.mp4'
                if not target.is_file():return self.respond(404,{'error':'Chưa có video lồng tiếng.'})
                return self.serve_audio(target,'download=1' in urlparse(self.path).query,'video/mp4',(job.get('file_name') or job['name']+'-long-tieng')+'.mp4')
            target=folder/(dub[2][-2:]+'.srt')
            if not target.is_file():return self.respond(404,{'error':'Chưa có phụ đề.'})
            self.send_response(200);data=target.read_bytes()
            self.send_header('Content-Type','application/x-subrip; charset=utf-8');self.send_header('Content-Length',str(len(data)))
            self.send_header('Content-Disposition',"attachment; filename=\"sub.srt\"; filename*=UTF-8''"+quote(job['name']+'-'+dub[2][-2:]+'.srt'))
            self.end_headers();self.wfile.write(data);return
        if path == '/update/check':
            if (ROOT/'.git').exists():return self.respond(200,{'git':True,'current':VERSION})
            try:
                plan=update.check()
                return self.respond(200,{k:v for k,v in plan.items() if k!='manifest'})
            except update.UpdateError as exc:return self.respond(502,{'error':str(exc)})
        if path == '/frames':
            items=[{'id':f.stem,'url':'/frames/'+f.stem} for f in sorted(FRAMES.glob('*.png'),key=lambda f:f.stat().st_mtime,reverse=True) if PROJECT.fullmatch(f.stem)]
            return self.respond(200,{'frames':items})
        if path == '/settings':
            return self.respond(200, output_folder.load(SETTINGS))
        if path == '/encoders':
            return self.respond(200, {'hardware':media_engine.hardware_encoders()})
        if path == '/storage':
            return self.respond(200, storage())
        match = re.fullmatch(r'/(jobs|download)/([a-f0-9]{32})', path)
        if match:
            kind, key = match.groups()
            job = load_job(key)
            if kind == 'jobs' and job:
                return self.respond(200, job)
            output = DATA / key / ('preview.mp4' if job and job.get('file') == 'preview.mp4' else 'review.mp4')
            if kind == 'download' and job and job['state'] == 'done' and output.is_file():
                self.send_response(200)
                self.send_header('Content-Type', 'video/mp4')
                self.send_header('Content-Disposition', "attachment; filename=\"review.mp4\"; filename*=UTF-8''"+quote(job.get('name','review')+('-xem-thu' if job.get('preview') else '')+'.mp4'))
                self.send_header('Content-Length', str(output.stat().st_size))
                self.end_headers()
                try:
                    with output.open('rb') as source:
                        while chunk := source.read(1024 * 1024):
                            self.wfile.write(chunk)
                except (BrokenPipeError,ConnectionResetError):
                    pass
                return
        self.respond(404, {'error': 'Không tìm thấy.'})

    def do_POST(self):
        if not self.allowed():
            return
        path = urlparse(self.path).path
        try:
            size = int(self.headers.get('Content-Length', '0'))
            local=self.headers.get('X-Local-Path')
            if local and (path in LOCAL_UPLOADS or re.fullmatch(r'/dub/[a-f0-9]{32}/voice',path)):
                src=local_file({'path':unquote(local)},LOCAL_UPLOADS.get(path,AUDIO_EXT))
                if path=='/upload':
                    # videos are hard-linked (instant, no extra space) instead of copied into the library
                    key=uuid.uuid4().hex;folder=DATA/key;folder.mkdir()
                    try:
                        how=link_or_copy(src,folder/'source')
                        data=dict(id=key,name=asset_store.clean_name(src.name),url='/media/video/'+key,local=how,**probe(folder/'source'))
                        (folder/'source.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
                    except BaseException:
                        shutil.rmtree(folder,ignore_errors=True);raise
                    return self.respond(200,data)
                if path=='/overlays/upload':
                    temp=DATA/'overlays'/(uuid.uuid4().hex+'.upload');link_or_copy(src,temp)
                    try:return self.respond(200,DUB.import_overlay(temp,src.name))
                    except dubbing.DubError as exc:return self.respond(exc.status,{'error':str(exc)})
                    finally:temp.unlink(missing_ok=True)
                # the other handlers read the request body: they read the local file instead (disk to disk)
                self.rfile=src.open('rb');size=src.stat().st_size
                self.headers.replace_header('X-Filename',quote(src.name)) if self.headers.get('X-Filename') else self.headers.add_header('X-Filename',quote(src.name))
            if path=='/local/pick-files':
                raw=json.loads(self.rfile.read(size)) if 0<size<=4096 else {}
                kinds=[k for k in raw.get('kinds',[]) if k in PICK_TYPES] or ['video']
                types=[t for k in kinds for t in PICK_TYPES[k]]
                chosen=output_folder.pick_files(str(raw.get('title') or 'Chọn file')[:120],types,raw.get('multiple') is not False)
                out=[]
                for p in chosen:
                    f=Path(p)
                    if f.is_file():out.append(dict(path=str(f),name=f.name,size=f.stat().st_size,type=MIME.get(f.suffix.lower(),'application/octet-stream')))
                return self.respond(200,{'files':out})
            if path=='/local/read-text':
                raw=json.loads(self.rfile.read(size)) if 0<size<=4096 else {}
                src=local_file(raw,('.srt','.txt','.json'))
                if src.stat().st_size>5*1024*1024:raise ValueError('File quá lớn.')
                return self.respond(200,{'text':src.read_text(encoding='utf-8-sig',errors='replace')})
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
            if path=='/audio/clone':
                if not 0<size<=10*1024*1024:raise ValueError('File mẫu giọng tối đa 10 MB.')
                data=self.rfile.read(size)
                if len(data)!=size:raise ValueError('Tải mẫu giọng bị gián đoạn.')
                key=self.headers.get('X-Api-Key','') or None
                return self.respond(200,ai33_audio.clone_voice(key,unquote(self.headers.get('X-Voice-Name','')),unquote(self.headers.get('X-Filename','sample.mp3')),data))
            if path in ('/audio/voices','/audio/create','/audio/dialogue','/audio/task','/audio/history','/audio/credits','/audio/cache','/audio/srt',
                        '/audio/dictionaries','/audio/dictionary/save','/audio/dictionary/delete','/audio/dictionary/preview','/audio/clone/delete'):
                if not 0 < size <= (4*1024*1024 if path in ('/audio/create','/audio/dialogue') else 262144):
                    raise ValueError('Yêu cầu audio quá lớn hoặc trống.')
                raw=json.loads(self.rfile.read(size))
                if not isinstance(raw,dict):
                    raise ValueError('Yêu cầu audio không hợp lệ.')
                if not AUDIO_SLOTS.acquire(blocking=False):
                    return self.respond(429, {'error':'Đang xử lý các yêu cầu âm thanh khác. Hãy chờ, không tạo lại tác vụ.'})
                try:
                    if path=='/audio/voices':
                        result=ai33_audio.voice_library(raw)
                    elif path in ('/audio/create','/audio/dialogue'):
                        result=(ai33_audio.create_tts if path=='/audio/create' else ai33_audio.create_dialogue)(raw)
                        aid=audio_files.asset_id(result['task_id'])
                        record=asset_store.write(AUDIO,aid,name=raw.get('file_name') or result['task_id'],source='ai33',task_id=result['task_id'],voice_id=raw.get('voice_id',''))
                        result['name']=record['name']
                    elif path=='/audio/history':
                        result=ai33_audio.list_tasks(raw)
                        for task in result['tasks']:
                            record=asset_store.read(AUDIO,audio_files.asset_id(task['task_id']))
                            task['name']=task.get('name') or record.get('name') or task['task_id']
                            aid=audio_files.asset_id(task['task_id'])
                            if (AUDIO/(aid+'.mp3')).is_file() and isinstance(record.get('duration'),(int,float)):task['asset']=asset_store.public(record)
                    elif path=='/audio/credits':
                        result=ai33_audio.credits(raw)
                    elif path=='/audio/cache':
                        result=audio_files.cache(raw,AUDIO)
                    elif path=='/audio/srt':
                        result=audio_files.subtitles(raw)
                    elif path=='/audio/dictionaries':
                        result=ai33_audio.dictionaries(raw)
                    elif path=='/audio/dictionary/save':
                        result=ai33_audio.save_dictionary(raw)
                    elif path=='/audio/dictionary/delete':
                        result=ai33_audio.delete_dictionary(raw)
                    elif path=='/audio/dictionary/preview':
                        result=ai33_audio.preview_dictionary(raw)
                    elif path=='/audio/clone/delete':
                        result=ai33_audio.delete_clone(raw)
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
            if path == '/image-upload':
                if not 0 < size <= 15*1024*1024:
                    return self.respond(413, {'error': 'Ảnh tối đa 15 MB.'})
                data = self.rfile.read(size)
                if len(data) != size:raise ValueError('Tải ảnh bị gián đoạn.')
                return self.respond(200, import_image(data,unquote(self.headers.get('X-Filename','anh.png'))))
            image_action=re.fullmatch(r'/images/([a-f0-9]{32})/(delete|as-frame)',path)
            if image_action:
                key,action=image_action.groups()
                if not (IMAGES/(key+'.png')).is_file():raise ValueError('Ảnh không còn trong kho.')
                if action=='as-frame':
                    shutil.copyfile(IMAGES/(key+'.png'),FRAMES/(key+'.png'))
                    return self.respond(200,{'id':key,'url':'/frames/'+key})
                for suffix in ('.png','.json'):(IMAGES/(key+suffix)).unlink(missing_ok=True)
                return self.respond(200,{'images':images()})
            if path in ('/secrets/save','/secrets/delete'):
                raw=json.loads(self.rfile.read(size)) if 0<size<=4096 else {}
                if not isinstance(raw,dict):raise ValueError('Yêu cầu không hợp lệ.')
                return self.respond(200,secrets_store.save(raw.get('provider'),raw.get('key')) if path.endswith('save') else secrets_store.delete(raw.get('provider')))
            if path == '/dub/images/upload':
                if not 0 < size <= 60*1024*1024:raise ValueError('Ảnh tối đa 60 MB.')
                name=asset_store.clean_name(unquote(self.headers.get('X-Filename','image.png')),'image.png')
                temp=DUB.image_dir/(uuid.uuid4().hex+'.upload')
                try:
                    temp.write_bytes(self.rfile.read(size))
                    try:return self.respond(200,DUB.import_image(temp,name))
                    except dubbing.DubError as exc:return self.respond(exc.status,{'error':str(exc)})
                finally:temp.unlink(missing_ok=True)
            dimg_del=re.fullmatch(r'/dub/images/([a-f0-9]{32})/delete',path)
            if dimg_del:
                try:DUB.delete_image(dimg_del[1])
                except dubbing.DubError as exc:return self.respond(exc.status,{'error':str(exc)})
                return self.respond(200,{'images':DUB.images()})
            if path == '/overlays/upload':
                if not 0 < size <= 4*1024**3:raise ValueError('File overlay tối đa 4 GB.')
                name=asset_store.clean_name(unquote(self.headers.get('X-Filename','overlay.mp4')),'overlay.mp4')
                temp=DATA/'overlays'/(uuid.uuid4().hex+'.upload')
                try:
                    with temp.open('wb') as out:
                        remaining=size
                        while remaining:
                            chunk=self.rfile.read(min(1024*1024,remaining))
                            if not chunk:raise ValueError('Tải overlay bị gián đoạn.')
                            out.write(chunk);remaining-=len(chunk)
                    try:return self.respond(200,DUB.import_overlay(temp,name))
                    except dubbing.DubError as exc:return self.respond(exc.status,{'error':str(exc)})
                finally:temp.unlink(missing_ok=True)
            if path=='/overlays/delete-many':
                raw=json.loads(self.rfile.read(size)) if 0<size<=64*1024 else {}
                ids=[o['id'] for o in DUB.overlays()] if raw.get('all') is True else raw.get('ids')
                if not isinstance(ids,list) or not all(isinstance(i,str) and PROJECT.fullmatch(i) for i in ids):raise ValueError('Danh sách overlay không hợp lệ.')
                for i in ids:
                    try:DUB.delete_overlay(i)
                    except dubbing.DubError:pass
                return self.respond(200,{'overlays':DUB.overlays(),'deleted':len(ids)})
            ov_delete=re.fullmatch(r'/overlays/([a-f0-9]{32})/delete',path)
            if ov_delete:
                try:DUB.delete_overlay(ov_delete[1])
                except dubbing.DubError as exc:return self.respond(exc.status,{'error':str(exc)})
                return self.respond(200,{'overlays':DUB.overlays()})
            voice=re.fullmatch(r'/dub/([a-f0-9]{32})/voice',path)
            if voice:
                if not 0 < size <= 100*1024*1024:raise ValueError('File giọng tối đa 100 MB.')
                if not (DATA/'dub'/voice[1]/'job.json').is_file():return self.respond(404,{'error':'Không tìm thấy tác vụ lồng tiếng.'})
                temp=DATA/'dub'/voice[1]/'upload.voice'
                try:
                    with temp.open('wb') as out:
                        remaining=size
                        while remaining:
                            chunk=self.rfile.read(min(1024*1024,remaining))
                            if not chunk:raise ValueError('Tải file giọng bị gián đoạn.')
                            out.write(chunk);remaining-=len(chunk)
                    try:return self.respond(200,DUB.use_voice(voice[1],temp))
                    except dubbing.DubError as exc:return self.respond(exc.status,{'error':str(exc)})
                finally:temp.unlink(missing_ok=True)
            if path=='/dub/demucs/install':return self.respond(200,dubbing.install_demucs())
            if path in ('/dub/queue','/dub/review','/dub/estimate','/dub/sample'):
                size=int(self.headers.get('Content-Length',0) or 0)
                if size>4*1024*1024:return self.respond(413,{'error':'Yêu cầu quá lớn.'})
                raw=json.loads(self.rfile.read(size)) if size else {}
                if not isinstance(raw,dict):return self.respond(400,{'error':'Yêu cầu không hợp lệ.'})
                try:
                    if path=='/dub/queue':return self.respond(200,DUB.set_parallel(raw.get('parallel')))
                    if path=='/dub/review':return self.respond(200,DUB.review(raw))
                    if path=='/dub/sample':return self.respond(200,DUB.voice_sample(raw))
                    return self.respond(200,DUB.estimate(raw))
                except dubbing.DubError as exc:return self.respond(exc.status,{'error':str(exc)})
            dub=re.fullmatch(r'/dub/(start|([a-f0-9]{32})/(continue|lines|texts|cancel|delete|editor))',path)
            if dub:
                if not 0 <= size <= 4*1024*1024:raise ValueError('Yêu cầu lồng tiếng quá lớn.')
                raw=json.loads(self.rfile.read(size)) if size else {}
                if not isinstance(raw,dict):raise ValueError('Yêu cầu lồng tiếng không hợp lệ.')
                try:
                    if dub[1]=='start':return self.respond(200,{'jobs':DUB.create(raw)})
                    key,action=dub[2],dub[3]
                    if action=='continue':return self.respond(200,DUB.proceed(key,raw))
                    if action=='lines':return self.respond(200,DUB.edit_paragraph(key,raw['paragraph']) if 'paragraph' in raw else DUB.edit_lines(key,raw.get('lines')))
                    if action=='texts':return self.respond(200,DUB.summary(DUB.edit_texts(key,raw)))
                    if action=='cancel':return self.respond(200,DUB.cancel(key))
                    if action=='delete':DUB.delete(key);return self.respond(200,{'jobs':DUB.jobs()})
                    vid=uuid.uuid4().hex;folder=DATA/vid;folder.mkdir()
                    try:
                        result=DUB.to_editor(key,lambda:folder/'source',lambda p,n:audio_files.import_audio(p,AUDIO,n))
                        name=DUB.load(key)['name']+' · lồng tiếng'
                        (folder/'source.json').write_text(json.dumps(dict(id=vid,name=name,url='/media/video/'+vid,**probe(folder/'source')),ensure_ascii=False),encoding='utf-8')
                    except BaseException:
                        shutil.rmtree(folder,ignore_errors=True);raise
                    return self.respond(200,{**result,'video_id':vid})
                except dubbing.DubError as exc:return self.respond(exc.status,{'error':str(exc)})
            if path=='/app/quit':
                # quit button in the header
                threading.Timer(.6,lambda:os._exit(0)).start()
                return self.respond(200,{'quitting':True})
            if path in ('/update/apply','/update/restart'):
                if (ROOT/'.git').exists():raise ValueError('Bản git clone: cập nhật bằng lệnh git pull.')
                with LOCK:busy=any(job.get('state') in ACTIVE for job in JOBS.values())
                if busy:raise ValueError('Đang xuất video. Chờ xuất xong rồi cập nhật/khởi động lại.')
                if path=='/update/restart':
                    # launch.py restarts the app when it exits with RESTART_CODE (started directly, it just stops).
                    threading.Timer(.6,lambda:os._exit(RESTART_CODE)).start()
                    return self.respond(200,{'restarting':True,'launcher':os.environ.get('REVIEW_LAUNCHER')=='1'})
                try:return self.respond(200,update.apply(log=lambda line:None))
                except update.UpdateError as exc:return self.respond(502,{'error':str(exc)})
            if path in ('/local/pick-folder','/local/scan','/local/import','/overlays/import-local'):
                raw=json.loads(self.rfile.read(size)) if 0<size<=8192 else {}
                if path=='/local/pick-folder':
                    title='Chọn thư mục chứa video overlay' if raw.get('kind')=='overlay' else 'Chọn thư mục chứa video cần lồng tiếng'
                    chosen=output_folder.pick(str(Path.home()),title)
                    return self.respond(200,{'folder':chosen,'cancelled':not chosen})
                if path=='/local/scan':
                    kinds=dubbing.OVERLAY_TYPES if raw.get('kind')=='overlay' else VIDEO_EXT+('.srt',)+AUDIO_EXT
                    return self.respond(200,{'files':scan_folder(raw,kinds)})
                if path=='/overlays/import-local':
                    src=local_file(raw,dubbing.OVERLAY_TYPES)
                    temp=DATA/'overlays'/(uuid.uuid4().hex+'.upload')
                    link_or_copy(src,temp)
                    try:return self.respond(200,DUB.import_overlay(temp,src.name))
                    except dubbing.DubError as exc:return self.respond(exc.status,{'error':str(exc)})
                    finally:temp.unlink(missing_ok=True)
                src=local_file(raw,VIDEO_EXT)
                key=uuid.uuid4().hex;folder=DATA/key;folder.mkdir()
                try:
                    how=link_or_copy(src,folder/'source')
                    metadata=probe(folder/'source')
                    data=dict(id=key,name=asset_store.clean_name(src.name),url='/media/video/'+key,local=how,**metadata)
                    (folder/'source.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
                    srt=src.with_suffix('.srt')
                    if srt.is_file() and srt.stat().st_size<=2*1024*1024:data={**data,'srt':srt.read_text(encoding='utf-8-sig',errors='replace'),'srt_name':srt.name}
                except BaseException:
                    shutil.rmtree(folder,ignore_errors=True);raise
                return self.respond(200,data)
            if path == '/upload':
                if not 0 < size <= 500 * 1024 * 1024:
                    return self.respond(413, {'error': 'Chọn video tối đa 500 MB.'})
                key = uuid.uuid4().hex
                folder = DATA / key
                folder.mkdir()
                remaining = size
                try:
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
                except BaseException:
                    # A rejected or interrupted upload must not leave a partial video on disk.
                    shutil.rmtree(folder,ignore_errors=True)
                    raise
                return self.respond(200,data)
            if path == '/storage/cleanup':
                if not 0 < size <= 256:
                    raise ValueError('Yêu cầu không hợp lệ.')
                raw = json.loads(self.rfile.read(size))
                days = raw.get('days') if isinstance(raw,dict) else None
                if isinstance(days,bool) or not isinstance(days,int) or not 1 <= days <= 3650:
                    raise ValueError('Số ngày phải từ 1 đến 3650.')
                return self.respond(200, cleanup(days))
            library=re.fullmatch(r'/library/(projects|templates|styles|presets|dubpresets|buildpresets)/(save|([a-f0-9]{32})/delete)',path)
            if library:
                if library[3]:
                    library_store.delete(DATA/'library',library[1],library[3])
                    return self.respond(200,{'items':library_store.items(DATA/'library',library[1])})
                if not 0 < size <= library_store.LIMIT:
                    raise ValueError('Dự án quá lớn để lưu (tối đa 512 KB).')
                return self.respond(200,library_store.save(DATA/'library',library[1],json.loads(self.rfile.read(size))))
            if path == '/media/loudness':
                raw=json.loads(self.rfile.read(size)) if 0 < size <= 1024 else {}
                job=raw.get('job') if isinstance(raw,dict) else None
                aid=raw.get('asset') if isinstance(raw,dict) else None
                if isinstance(job,str) and PROJECT.fullmatch(job):
                    record=load_job(job)
                    target=DATA/job/'review.mp4'
                    if not record or record.get('state')!='done' or record.get('preview') or not target.is_file():raise ValueError('Chưa có bản xuất hoàn chỉnh của video này. Xuất video trước rồi đo.')
                elif isinstance(aid,str) and PROJECT.fullmatch(aid) and (AUDIO/(aid+'.mp3')).is_file():target=AUDIO/(aid+'.mp3')
                else:raise ValueError('Chọn bản xuất hoặc MP3 cần đo.')
                return self.respond(200,media_engine.loudness(target))
            if path == '/settings':
                if not 0 < size <= 4096:
                    raise ValueError('Cài đặt không hợp lệ.')
                return self.respond(200, output_folder.save(SETTINGS,json.loads(self.rfile.read(size))))
            if path == '/settings/pick-folder':
                chosen=output_folder.pick(output_folder.load(SETTINGS)['output_dir'])
                if not chosen:return self.respond(200,{**output_folder.load(SETTINGS),'cancelled':True})
                return self.respond(200, output_folder.save(SETTINGS,{'output_dir':chosen}))
            if path == '/settings/open-folder':
                # Only the configured folder or a file this app saved there can be revealed.
                raw=json.loads(self.rfile.read(size)) if 0 < size <= 1024 else {}
                job=load_job(raw.get('job','')) if isinstance(raw,dict) and isinstance(raw.get('job'),str) and PROJECT.fullmatch(raw['job']) else None
                target=job.get('saved_path') if job else None
                output_folder.reveal(target if target and Path(target).is_file() else output_folder.check_dir(output_folder.load(SETTINGS)['output_dir']))
                return self.respond(200, {'ok':True})
            video_delete=re.fullmatch(r'/media/video/([a-f0-9]{32})/delete',path)
            if video_delete:
                if not (DATA/video_delete[1]/'source').is_file():raise ValueError('Video không còn trong kho.')
                delete_project(video_delete[1])
                return self.respond(200, storage())
            delete_match=re.fullmatch(r'/audio/([a-f0-9]{32})/delete',path)
            if delete_match:
                delete_audio(delete_match[1])
                return self.respond(200, storage())
            if path == '/design':
                if not 0 < size <= 65536:
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
                if not 0 < size <= 65536:
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
                    command,plan,fallback=compose(folder,opts)
                except ValueError:
                    with LOCK:
                        JOBS.pop(key, None)
                    raise
                name=asset_store.clean_name(opts.get('project_name'),'review-video').removesuffix('.mp4')
                cancel=threading.Event()
                with LOCK:CANCELS[key]=cancel
                threading.Thread(target=render,args=(key,command,plan,name,cancel,fallback),daemon=True).start()
                return self.respond(202, {'id': key})
            self.respond(404, {'error': 'Không tìm thấy.'})
        except ai33_audio.AudioError as error:
            self.respond(error.status, {'error':str(error)})
        except ValueError as error:
            self.respond(400, {'error': str(error)})
        except (KeyError, TypeError, subprocess.SubprocessError):
            self.respond(400, {'error': 'Dữ liệu không hợp lệ. Dùng clip video tối đa 30 phút.'})


if __name__ == '__main__':
    address = ('127.0.0.1', int(os.environ.get('PORT', '8000')))
    if keep_days():
        swept = cleanup(keep_days())
        if swept['removed']:
            print(f"Removed {swept['removed']} video project(s) idle for over {keep_days()} days ({swept['freed']//1048576} MB).", flush=True)
    threading.Thread(target=media_engine.hardware_encoders,daemon=True).start()
    print(f'Review Studio {VERSION} running on port {address[1]}', flush=True)
    ThreadingHTTPServer(address, Handler).serve_forever()
