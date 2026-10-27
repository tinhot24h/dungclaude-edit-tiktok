"""Deterministic two-track trim/retime/mix and native-resolution video export."""
import json
import math
import subprocess
from pathlib import Path
from design import artwork,layout,frame_box,video_box
from fonts import FONTS

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


def plan(opts,video,audio=None):
    vs=number(opts,'video_start',0,0,video['duration'])
    ve=number(opts,'video_end',0,0,video['duration']+.05) or video['duration']
    ve=min(ve,video['duration'])
    vr=number(opts,'video_speed',1,.25,4)
    if ve-vs<.05:raise ValueError('Đoạn video cần dài ít nhất 0,05 giây.')
    vdur=(ve-vs)/vr
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
    if not .05<=duration<=1800:raise ValueError('Thời lượng xuất phải từ 0,05 giây đến 30 phút.')
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
    return dict(video_start=vs,video_end=ve,video_speed=vr,video_duration=vdur,audio_start=astart,audio_end=aend,
                audio_speed=ar,audio_offset=delay,audio_duration=adur,active_audio=active,audio_mode=mode,
                audio_volume=volume,original_volume=original,duration=duration,resolution=resolution,
                width=RESOLUTIONS[resolution][0],height=RESOLUTIONS[resolution][1],quality=quality,warnings=warnings)


def tempo(rate):
    filters=[]
    while rate<.5-1e-8:filters.append('atempo=0.5');rate/=.5
    while rate>2+1e-8:filters.append('atempo=2');rate/=2
    filters.append(f'atempo={rate:.9f}')
    return ','.join(filters)


def build(folder,opts,video_path,video,audio_path=None,audio=None,frame_path=None):
    folder=Path(folder);p=plan(opts,video,audio)
    ow,oh=p['width'],p['height'];scale=ow/720
    box=video_box(opts);vw=max(2,round(box['width']*scale));vh=max(2,round(box['height']*scale))
    angle=float(opts.get('video_rotation',0));rad=math.radians(angle)
    rw=abs(vw*math.cos(rad))+abs(vh*math.sin(rad));rh=abs(vh*math.cos(rad))+abs(vw*math.sin(rad))
    if rw*rh>48000000:raise ValueError('Zoom/kích thước và góc xoay quá lớn cho độ phân giải này. Giảm zoom hoặc độ phân giải.')
    (folder/'overlay.png').write_bytes(artwork(opts))
    args=['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y','-ss',str(p['video_start']),'-t',str(p['video_end']-p['video_start']),'-i',str(video_path),'-i','overlay.png']
    graph=[]
    source='[0:v]setpts=(PTS-STARTPTS)/'+str(p['video_speed'])+',fps=30,format=rgba,'
    fit=opts.get('video_fit','cover')
    if fit=='cover':source+=f'scale={vw}:{vh}:force_original_aspect_ratio=increase,crop={vw}:{vh},'
    elif fit=='contain':source+=f'scale={vw}:{vh}:force_original_aspect_ratio=decrease,pad={vw}:{vh}:(ow-iw)/2:(oh-ih)/2:color=0x00000000,'
    else:source+=f'scale={vw}:{vh},'
    source+=f'rotate={rad:.12f}:ow=rotw({rad:.12f}):oh=roth({rad:.12f}):c=none,setsar=1,tpad=stop_mode=clone:stop_duration={p["duration"]},trim=duration={p["duration"]}[clip]'
    graph.append(source)
    graph.append(f'color=c={opts["color"].replace("#","0x")}:s={ow}x{oh}:r=30:d={p["duration"]},format=rgba[base]')
    x=box['x']*scale;y=box['y']*scale
    graph.append(f'[base][clip]overlay=x={x}+({vw}-overlay_w)/2:y={y}+({vh}-overlay_h)/2:shortest=1:format=auto[placed]')
    graph.append(f'[1:v]scale={ow}:{oh}:flags=lanczos[art]')
    graph.append('[placed][art]overlay=0:0:format=auto[design]')
    next_input=2;top='design'
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
        graph.append(f'[0:a:0]asetpts=PTS-STARTPTS,{tempo(p["video_speed"])},volume={p["original_volume"]/100},aresample=48000,aformat=channel_layouts=stereo,apad,atrim=duration={p["duration"]}[original]')
        labels.append('original')
    if p['active_audio']:
        args+=['-ss',str(p['audio_start']),'-t',str(p['audio_end']-p['audio_start']),'-i',str(audio_path)]
        graph.append(f'[{next_input}:a:0]asetpts=PTS-STARTPTS,{tempo(p["audio_speed"])},volume={p["audio_volume"]/100},aresample=48000,aformat=channel_layouts=stereo,adelay={round(p["audio_offset"]*1000)}:all=1,apad,atrim=duration={p["duration"]}[voice]')
        labels.append('voice')
    if len(labels)==2:graph.append('[original][voice]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95:level=false[aout]')
    elif labels:graph.append(f'[{labels[0]}]alimiter=limit=0.95:level=false[aout]')
    script=folder/'render.ffgraph';script.write_text(';\n'.join(graph),encoding='utf-8')
    args+=['-filter_complex_threads','1','-filter_complex_script','render.ffgraph','-map','[out]']
    if labels:args+=['-map','[aout]','-c:a','aac','-b:a','192k']
    args+=['-c:v','libx264','-preset','veryfast','-crf','18' if p['quality']=='high' else '23','-threads','2','-r','30','-pix_fmt','yuv420p','-t',str(p['duration']),'-movflags','+faststart','-progress','progress.txt','review.mp4']
    return args,p
