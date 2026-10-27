"""Deterministic two-track trim/retime/mix and native-resolution video export."""
import json
import re
import math
import subprocess
from pathlib import Path
from design import artwork,layout,frame_box,video_box
from fonts import FONTS

MAX_SECONDS=1800  # longest source video and export, shared with app.probe
MAX_PIECES=60
HARDWARE=('h264_nvenc','h264_qsv','h264_amf','h264_videotoolbox')
RESOLUTIONS={'720':(720,1280),'1080':(1080,1920),'2k':(1440,2560),'4k':(2160,3840)}


def probe(path):
    result=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type,width,height','-of','json',str(path)],capture_output=True,text=True,check=True,timeout=30)
    data=json.loads(result.stdout);duration=float(data['format']['duration'])
    if not math.isfinite(duration) or not .02<duration<=86400:raise ValueError('Thời lượng nguồn không hợp lệ hoặc vượt 24 giờ.')
    video=next((s for s in data['streams'] if s.get('codec_type')=='video'),None)
    return dict(duration=duration,has_audio=any(s.get('codec_type')=='audio' for s in data['streams']),has_video=bool(video),
                width=video.get('width',0) if video else 0,height=video.get('height',0) if video else 0,bytes=Path(path).stat().st_size)


def number(opts,key,default,lo,hi):
    value=opts.get(key,default)
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not lo<=value<=hi:raise ValueError('Thông số không hợp lệ: '+key)
    return float(value)


def keep(cuts,start,end):
    """Source ranges kept after removing `cuts` ([[a,b],...] in source seconds) from start..end."""
    if not isinstance(cuts,list) or len(cuts)>200:raise ValueError('Danh sách đoạn xóa không hợp lệ.')
    removed=[]
    for cut in cuts:
        if not isinstance(cut,list) or len(cut)!=2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in cut) or cut[0]>=cut[1]:
            raise ValueError('Đoạn xóa không hợp lệ.')
        removed.append((max(start,float(cut[0])),min(end,float(cut[1]))))
    segments=[];at=start
    for a,b in sorted(r for r in removed if r[1]-r[0]>1e-6):
        if a-at>=.01:segments.append((at,a))
        at=max(at,b)
    if end-at>=.01:segments.append((at,end))
    return segments


def ordered(value,total):
    """Video pieces in playback order ([[a,b],...] source seconds); pieces may be reordered or repeated."""
    if value in (None,[]):return []
    if not isinstance(value,list) or len(value)>MAX_PIECES:raise ValueError(f'Tối đa {MAX_PIECES} đoạn video.')
    out=[]
    for item in value:
        if not isinstance(item,list) or len(item)!=2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in item):
            raise ValueError('Đoạn video không hợp lệ.')
        a,b=max(0.0,float(item[0])),min(float(total),float(item[1]))
        if b-a<.02:raise ValueError('Mỗi đoạn video cần dài ít nhất 0,02 giây.')
        out.append((a,b))
    return out


def choice(opts,key,default,allowed):
    value=opts.get(key,default)
    if value not in allowed:raise ValueError('Thông số không hợp lệ: '+key)
    return value


def plan(opts,video,audio=None,music=None):
    vs=number(opts,'video_start',0,0,video['duration'])
    ve=number(opts,'video_end',0,0,video['duration']+.05) or video['duration']
    ve=min(ve,video['duration'])
    vr=number(opts,'video_speed',1,.25,4)
    if ve-vs<.05:raise ValueError('Đoạn video cần dài ít nhất 0,05 giây.')
    segments=ordered(opts.get('video_segments'),video['duration']) or keep(opts.get('video_cuts',[]),vs,ve)
    if opts.get('video_segments'):vs,ve=min(a for a,_ in segments),max(b for _,b in segments)
    if len(segments)>MAX_PIECES:raise ValueError(f'Tối đa {MAX_PIECES} đoạn video.')
    if sum(b-a for a,b in segments)<.05:raise ValueError('Đoạn video còn lại sau khi xóa cần dài ít nhất 0,05 giây.')
    vdur=sum(b-a for a,b in segments)/vr
    mode=opts.get('audio_mode','replace' if audio else 'original')
    if mode not in ('original','replace','mix'):raise ValueError('Chế độ âm thanh không hợp lệ.')
    if mode in ('replace','mix') and not audio:raise ValueError('Chọn MP3 trước khi thay/trộn âm thanh.')
    active=audio is not None and mode!='original'
    astart=aend=adur=0
    ar=number(opts,'audio_speed',1,.25,4)
    delay=number(opts,'audio_offset',0,0,1800)
    if active:
        astart=number(opts,'audio_start',0,0,audio['duration'])
        aend=number(opts,'audio_end',0,0,audio['duration']+.05) or audio['duration']
        aend=min(aend,audio['duration'])
        if aend-astart<.05:raise ValueError('Đoạn MP3 cần dài ít nhất 0,05 giây.')
        adur=(aend-astart)/ar+delay
    policy=opts.get('duration_policy','audio' if active else 'video')
    if policy not in ('audio','video','shortest'):raise ValueError('Cách khớp thời lượng không hợp lệ.')
    duration=(adur if policy=='audio' else min(vdur,adur) if policy=='shortest' else vdur) if active else vdur
    if not .05<=duration<=MAX_SECONDS:raise ValueError('Thời lượng xuất phải từ 0,05 giây đến 30 phút.')
    resolution=opts.get('resolution','720')
    if resolution not in RESOLUTIONS:raise ValueError('Độ phân giải không hợp lệ.')
    quality=opts.get('quality','standard')
    if quality not in ('standard','high'):raise ValueError('Chất lượng xuất không hợp lệ.')
    volume=number(opts,'audio_volume',100,0,300)
    original=number(opts,'original_volume',100,0,300)
    warnings=[]
    if active and abs(vdur-adur)>.05:
        if duration>vdur+.05:warnings.append(f'Giữ hình cuối thêm {duration-vdur:.2f}s để khớp MP3.')
        if duration<vdur-.05:warnings.append(f'Cắt {vdur-duration:.2f}s cuối track video.')
        if duration<adur-.05:warnings.append(f'Cắt {adur-duration:.2f}s cuối track MP3.')
        if duration>adur+.05:warnings.append(f'Đệm im lặng {duration-adur:.2f}s cuối MP3.')
    fps=choice(opts,'fps',30,(30,60))
    motion=choice(opts,'video_motion','none',('none','zoom_in','zoom_out'))
    amount=number(opts,'motion_amount',12,0,50)
    loudness=choice(opts,'loudness','off',('off','tiktok'))
    encoder=choice(opts,'encoder','cpu',('cpu',)+HARDWARE)
    track=None
    if music:
        mstart=number(opts,'music_start',0,0,music['duration'])
        if music['duration']-mstart<.05:raise ValueError('Đoạn nhạc nền cần dài ít nhất 0,05 giây.')
        if not isinstance(opts.get('music_loop',True),bool) or not isinstance(opts.get('music_duck',True),bool):raise ValueError('Tùy chọn nhạc nền không hợp lệ.')
        track=dict(start=mstart,volume=number(opts,'music_volume',30,0,300),fade_in=number(opts,'music_fade_in',1,0,10),
                   fade_out=number(opts,'music_fade_out',2,0,10),loop=opts.get('music_loop',True),duck=opts.get('music_duck',True))
    preview=opts.get('preview_at')
    if preview is not None:
        preview=number(opts,'preview_at',0,0,duration)
        if duration-preview<.05:preview=max(0,duration-5)
    return dict(video_start=vs,video_end=ve,video_speed=vr,video_duration=vdur,video_segments=segments,fps=fps,motion=motion,motion_amount=amount,
                loudness=loudness,encoder=encoder,music=track,preview_at=preview,
                output_duration=min(5,duration-preview) if preview is not None else duration,audio_start=astart,audio_end=aend,
                audio_speed=ar,audio_offset=delay,audio_duration=adur,active_audio=active,audio_mode=mode,
                audio_volume=volume,original_volume=original,duration=duration,resolution=resolution,
                width=RESOLUTIONS[resolution][0],height=RESOLUTIONS[resolution][1],quality=quality,warnings=warnings)


def tempo(rate):
    filters=[]
    while rate<.5-1e-8:filters.append('atempo=0.5');rate/=.5
    while rate>2+1e-8:filters.append('atempo=2');rate/=2
    filters.append(f'atempo={rate:.9f}')
    return ','.join(filters)


def encoder_args(encoder,quality):
    high=quality=='high'
    if encoder=='h264_nvenc':return ['-c:v','h264_nvenc','-preset','p4','-rc','vbr','-cq','19' if high else '24','-b:v','0','-pix_fmt','yuv420p']
    if encoder=='h264_qsv':return ['-c:v','h264_qsv','-global_quality','19' if high else '24','-pix_fmt','nv12']
    if encoder=='h264_amf':return ['-c:v','h264_amf','-quality','balanced','-rc','cqp','-qp_i','19' if high else '24','-qp_p','19' if high else '24','-pix_fmt','yuv420p']
    if encoder=='h264_videotoolbox':return ['-c:v','h264_videotoolbox','-q:v','75' if high else '62','-pix_fmt','yuv420p']
    return ['-c:v','libx264','-preset','veryfast','-crf','18' if high else '23','-threads','2','-pix_fmt','yuv420p']


_ENCODERS=None


def hardware_encoders():
    """Hardware H.264 encoders that can really open on this machine (cached after the first probe)."""
    global _ENCODERS
    if _ENCODERS is None:
        found=[]
        try:
            listed=subprocess.run(['ffmpeg','-hide_banner','-encoders'],capture_output=True,text=True,timeout=20).stdout
            for name in HARDWARE:
                if name not in listed:continue
                test=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-f','lavfi','-i','color=s=256x256:d=0.2',
                                     '-frames:v','3',*encoder_args(name,'standard'),'-f','null','-'],capture_output=True,timeout=20)
                if test.returncode==0:found.append(name)
        except (OSError,subprocess.SubprocessError):pass
        _ENCODERS=found
    return list(_ENCODERS)


def build(folder,opts,video_path,video,audio_path=None,audio=None,frame_path=None,music_path=None,music=None):
    folder=Path(folder);p=plan(opts,video,audio,music)
    ow,oh=p['width'],p['height'];scale=ow/720;fps=p['fps'];duration=p['duration']
    box=video_box(opts);vw=max(2,round(box['width']*scale));vh=max(2,round(box['height']*scale))
    angle=float(opts.get('video_rotation',0));rad=math.radians(angle)
    rw=abs(vw*math.cos(rad))+abs(vh*math.sin(rad));rh=abs(vh*math.cos(rad))+abs(vw*math.sin(rad))
    if rw*rh>48000000:raise ValueError('Zoom/kích thước và góc xoay quá lớn cho độ phân giải này. Giảm zoom hoặc độ phân giải.')
    (folder/'overlay.png').write_bytes(artwork(opts))
    args=['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y']
    pieces=p['video_segments'];count=len(pieces)
    # Each piece is its own seeked input so reordered pieces never buffer the whole source.
    for a,b in pieces:args+=['-ss',str(a),'-t',str(b-a),'-i',str(video_path)]
    art=count;args+=['-i','overlay.png']
    graph=[]
    if count>1:
        for i in range(count):graph.append(f'[{i}:v]setpts=PTS-STARTPTS,fps={fps},setsar=1[piece{i}]')
        source=''.join(f'[piece{i}]' for i in range(count))+f'concat=n={count}:v=1:a=0,setpts=PTS/{p["video_speed"]},fps={fps},format=rgba,'
    else:source='[0:v]setpts=(PTS-STARTPTS)/'+str(p['video_speed'])+f',fps={fps},format=rgba,'
    fit=opts.get('video_fit','cover')
    if fit=='cover':source+=f'scale={vw}:{vh}:force_original_aspect_ratio=increase,crop={vw}:{vh},'
    elif fit=='contain':source+=f'scale={vw}:{vh}:force_original_aspect_ratio=decrease,pad={vw}:{vh}:(ow-iw)/2:(oh-ih)/2:color=0x00000000,'
    else:source+=f'scale={vw}:{vh},'
    if p['motion']!='none' and p['motion_amount']>0:
        k=p['motion_amount']/100
        f=f'(1+{k}*t/{duration})' if p['motion']=='zoom_in' else f'(1+{k}*(1-t/{duration}))'
        source+=(f"scale=w='trunc({vw}*{f}/2)*2':h='trunc({vh}*{f}/2)*2':eval=frame,"
                 f"crop={vw}:{vh}:x='(trunc({vw}*{f}/2)*2-{vw})/2':y='(trunc({vh}*{f}/2)*2-{vh})/2',")
    source+=f'rotate={rad:.12f}:ow=rotw({rad:.12f}):oh=roth({rad:.12f}):c=none,setsar=1,tpad=stop_mode=clone:stop_duration={duration},trim=duration={duration}[clip]'
    graph.append(source)
    graph.append(f'color=c={"0x000000" if opts.get("background")=="none" else opts["color"].replace("#","0x")}:s={ow}x{oh}:r={fps}:d={duration},format=rgba[base]')
    x=box['x']*scale;y=box['y']*scale
    graph.append(f'[base][clip]overlay=x={x}+({vw}-overlay_w)/2:y={y}+({vh}-overlay_h)/2:shortest=1:format=auto[placed]')
    graph.append(f'[{art}:v]scale={ow}:{oh}:flags=lanczos[art]')
    graph.append('[placed][art]overlay=0:0:format=auto[design]')
    next_input=art+1;top='design'
    if opts['frame_style']=='custom':
        if not frame_path:raise ValueError('Thiếu khung PNG.')
        args+=['-i',str(frame_path)];b=frame_box(opts);w=max(1,round(b['width']*scale));h=max(1,round(b['height']*scale))
        graph.append(f'[{next_input}:v]format=rgba,scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=0x00000000,colorchannelmixer=aa={opts["frame_opacity"]/100}[custom]')
        graph.append(f'[design][custom]overlay={round(b["x"]*scale)}:{round(b["y"]*scale)}:format=auto[framed]')
        next_input+=1;top='framed'
    textfilters=[]
    for item in layout(opts):
        font='../../assets/'+FONTS[item['font']][0]
        for li,runs in enumerate(item['line_runs']):
            for wi,run in enumerate(runs):
                if not run['text'].strip():continue
                filename=f'{item["key"]}-{li}-{wi}.txt';(folder/filename).write_text(run['text'],encoding='utf-8')
                textfilters.append(f'drawtext=fontfile={font}:textfile={filename}:expansion=none:fontsize={item["size"]*scale}:fontcolor={item["color"].replace("#","0x")}:x={run["x"]*scale}:y={(item.get("content_y",item["y"])+li*(item["size"]+item["gap"]))*scale}:borderw={round(item["outline"]*scale)}:bordercolor={item["outline_color"].replace("#","0x")}')
    graph.append(f'[{top}]'+(','.join(textfilters) if textfilters else 'null')+',format=yuv420p[out]')
    labels=[]
    if video['has_audio'] and (not p['active_audio'] or p['audio_mode']=='mix'):
        if count>1:
            for i in range(count):graph.append(f'[{i}:a:0]asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,apad,atrim=duration={pieces[i][1]-pieces[i][0]}[sound{i}]')
            graph.append(''.join(f'[sound{i}]' for i in range(count))+f'concat=n={count}:v=0:a=1[joined]')
        graph.append(('[joined]' if count>1 else '[0:a:0]asetpts=PTS-STARTPTS,')+f'{tempo(p["video_speed"])},volume={p["original_volume"]/100},aresample=48000,aformat=channel_layouts=stereo,apad,atrim=duration={duration}[original]')
        labels.append('original')
    music_track=p['music']
    duck=bool(music_track and music_track['duck'] and p['active_audio'])
    if p['active_audio']:
        args+=['-ss',str(p['audio_start']),'-t',str(p['audio_end']-p['audio_start']),'-i',str(audio_path)]
        graph.append(f'[{next_input}:a:0]asetpts=PTS-STARTPTS,{tempo(p["audio_speed"])},volume={p["audio_volume"]/100},aresample=48000,aformat=channel_layouts=stereo,adelay={round(p["audio_offset"]*1000)}:all=1,apad,atrim=duration={duration}'+(',asplit=2[voice][voicekey]' if duck else '[voice]'))
        labels.append('voice');next_input+=1
    if music_track:
        args+=(['-stream_loop','-1'] if music_track['loop'] else [])+['-ss',str(music_track['start']),'-i',str(music_path)]
        chain=f'[{next_input}:a:0]asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,volume={music_track["volume"]/100},apad,atrim=duration={duration}'
        if music_track['fade_in']>0:chain+=f',afade=t=in:st=0:d={min(music_track["fade_in"],duration)}'
        if music_track['fade_out']>0:
            fade=min(music_track['fade_out'],duration);chain+=f',afade=t=out:st={duration-fade}:d={fade}'
        graph.append(chain+('[musicraw]' if duck else '[music]'))
        if duck:graph.append('[musicraw][voicekey]sidechaincompress=threshold=0.03:ratio=8:attack=15:release=350[music]')
        labels.append('music');next_input+=1
    finish=('loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000,' if p['loudness']=='tiktok' else '')+'alimiter=limit=0.95:level=false[aout]'
    if len(labels)>1:graph.append(''.join(f'[{label}]' for label in labels)+f'amix=inputs={len(labels)}:duration=longest:normalize=0,{finish}')
    elif labels:graph.append(f'[{labels[0]}]{finish}')
    script=folder/'render.ffgraph';script.write_text(';\n'.join(graph),encoding='utf-8')
    args+=['-filter_complex_threads','1','-filter_complex_script','render.ffgraph','-map','[out]']
    if labels:args+=['-map','[aout]','-c:a','aac','-b:a','192k']
    output='preview.mp4' if p['preview_at'] is not None else 'review.mp4'
    if p['preview_at'] is not None:args+=['-ss',str(p['preview_at'])]
    args+=[*encoder_args(p['encoder'],p['quality']),'-r',str(fps),'-t',str(p['output_duration']),'-movflags','+faststart','-progress','progress.txt',output]
    p['output']=output
    return args,p


def loudness(path):
    """Integrated loudness (LUFS), loudness range and true peak of a file's first audio stream (EBU R128)."""
    run=subprocess.run(['ffmpeg','-hide_banner','-nostdin','-i',str(path),'-map','0:a:0','-af','ebur128=peak=true','-f','null','-'],capture_output=True,text=True,timeout=600)
    summary=run.stderr[run.stderr.rfind('Summary:'):]
    def value(label):
        match=re.search(label+r':\s+(-?[\d.]+|-inf)',summary)
        return None if not match or match[1]=='-inf' else float(match[1])
    if run.returncode or 'Summary:' not in run.stderr:raise ValueError('Không đo được âm lượng: file không có âm thanh hoặc bị lỗi.')
    return dict(lufs=value('I'),lra=value('LRA'),true_peak=value('Peak'))
