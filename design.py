"""Shared geometry, editable text layout and portable RGBA frame artwork."""
import math
import re
import struct
import zlib
from fonts import FONTS, width, wrap

W, H = 720, 1280
FRAMES = ('pink','glass','gold','minimal','neon','ribbon','none','custom')
# Text layers: title and body plus up to six extra captions, each with its own style and on-screen time.
TEXT_KEYS = ('title','body','text1','text2','text3','text4','text5','text6')
TEXT_LIMITS = {'title':160,'body':600,**{k:300 for k in TEXT_KEYS[2:]}}
TEXT_LABELS = {'title':'Tiêu đề','body':'Nội dung',**{k:'Chữ '+k[4:] for k in TEXT_KEYS[2:]}}


def settings(raw):
    if not isinstance(raw, dict):
        raise ValueError('Yêu cầu không hợp lệ.')
    out = dict(raw)
    out.setdefault('units','percent')
    if out['units'] not in ('px','percent'):
        raise ValueError('Đơn vị không hợp lệ.')
    px = out['units'] == 'px'
    out.setdefault('template','pink')
    if out['template'] not in ('pink','blue'):
        raise ValueError('Mẫu không hợp lệ.')
    out.setdefault('frame_style','pink' if out['template']=='pink' else 'none')
    if out['frame_style'] not in FRAMES:
        raise ValueError('Khung không hợp lệ.')
    out.setdefault('background','solid')
    if out['background'] not in ('solid','gradient','none'):
        raise ValueError('Kiểu nền không hợp lệ.')
    for key,default in dict(color='#fad9e9',color2='#cbb9ef',frame_color='#f69fbe',border_color='#fff3e7',
                            title_color='#fff36a',body_color='#ffffff',title_outline_color='#342333',
                            body_outline_color='#342333',**{k+'_color':'#ffffff' for k in TEXT_KEYS[2:]},
                            **{k+'_outline_color':'#000000' for k in TEXT_KEYS[2:]},**{k+'_box_color':'#000000' for k in TEXT_KEYS}).items():
        out.setdefault(key,default)
        if not isinstance(out[key],str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',out[key]):
            raise ValueError('Mã màu không hợp lệ: '+key)
    spec = dict(fade_start=(44,0,90),fade_height=(18,2,60),opacity=(100,0,100),
                frame_x=(50,0,100),frame_y=(62,0,95),frame_width=(90,20,100),
                frame_height=(26,8,60),frame_opacity=(100,0,100),gloss=(65,0,100),
                zoom=(100,50,200),video_x=(0,-80,80),video_y=(0,-80,80),video_zoom=(100,25,400),video_rotation=(0,-180,180))
    if px:
        spec.update(fade_start=(563,0,1152),fade_height=(230,16,768),
                    frame_x=(36,-720,720),frame_y=(794,-1280,1280),
                    frame_width=(648,80,1440),frame_height=(333,60,2560),
                    video_x=(0,-2160,720),video_y=(0,-3840,1280),
                    video_width=(720,180,2160),video_height=(1280,320,3840))
    out.setdefault('video_fit','cover')
    out.setdefault('video_flip','none')
    if out['video_flip'] not in ('none','h','v','hv'):raise ValueError('Kiểu lật video không hợp lệ.')
    if out['video_fit'] not in ('cover','contain','stretch'):raise ValueError('Cách đặt video không hợp lệ.')
    for index,name in enumerate(TEXT_KEYS):
        extra=index-2
        spec.update({name+'_size':(30 if name=='title' else 22 if name=='body' else 28,12,144),
                     name+'_x':(50,0,100),name+'_y':(64 if name=='title' else 73 if name=='body' else 25+5*extra,0,98),
                     name+'_width':(76,20,100),name+'_height':(0,0,1280),name+'_outline':(1 if extra<0 else 2,0,5),name+'_gap':(4,0,24),name+'_word':(0,0,60),name+'_letter':(0,0,40),name+'_opacity':(100,0,100),
                     name+'_start':(0,0,1800),name+'_end':(0,0,1800),
                     name+'_box_opacity':(70,0,100),name+'_box_pad':(14,0,60),name+'_box_radius':(12,0,60)})
        if px:
            spec.update({name+'_x':(86,0,719),name+'_y':(819 if name=='title' else 934 if name=='body' else 300+60*extra,0,1270),
                         name+'_width':(548,60,720)})
        out.setdefault(name+'_font','sans' if name=='body' else 'sans-bold')
        out.setdefault(name+'_box','none')
        if out[name+'_box'] not in ('none','solid'):raise ValueError('Kiểu nền chữ không hợp lệ.')
        out.setdefault(name+'_align','center')
        out.setdefault(name+'_valign','top')
        out.setdefault(name+'_case','none')
        if out[name+'_case'] not in CASES:raise ValueError('Kiểu chữ hoa/thường không hợp lệ.')
        if out[name+'_valign'] not in ('top','middle','bottom'):raise ValueError('Căn dọc không hợp lệ.')
        if out[name+'_font'] not in FONTS or out[name+'_align'] not in ('left','center','right','justify'):
            raise ValueError('Font hoặc căn chữ không hợp lệ.')
    for key,(default,low,high) in spec.items():
        value=out.get(key,default)
        if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or not low<=value<=high:
            raise ValueError('Thông số ngoài giới hạn: '+key)
        out[key]=round(value,1)
    for name in TEXT_KEYS:
        if out[name+'_end'] and out[name+'_end']<=out[name+'_start']+.05:
            raise ValueError(TEXT_LABELS[name]+': thời điểm kết thúc phải sau thời điểm bắt đầu (0 = tới hết video).')
    out['images']=image_layers(out.get('images',[]))
    if out['frame_style']=='custom':
        if not isinstance(out.get('frame_id'),str) or not re.fullmatch('[a-f0-9]{32}',out['frame_id']):
            raise ValueError('Hãy tải khung PNG từ máy trước.')
    return out


MAX_IMAGES=12
IMAGE_SPEC=dict(x=(-720,1440),y=(-1280,2560),width=(8,2160),height=(8,3840),opacity=(0,100),start=(0,1800),end=(0,1800),rotation=(-180,180))


def image_layers(value):
    """Image/logo/sticker layers in 720x1280 design pixels, drawn above the frame and below the text."""
    if value in (None,[]):return []
    if not isinstance(value,list) or len(value)>MAX_IMAGES:raise ValueError(f'Tối đa {MAX_IMAGES} lớp ảnh.')
    out=[]
    for item in value:
        if not isinstance(item,dict) or not isinstance(item.get('id'),str) or not re.fullmatch('[a-f0-9]{32}',item['id']):raise ValueError('Lớp ảnh không hợp lệ.')
        layer=dict(id=item['id'])
        for key,(low,high) in IMAGE_SPEC.items():
            v=item.get(key,{'opacity':100}.get(key,0))
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not low<=v<=high:raise ValueError('Thông số lớp ảnh ngoài giới hạn: '+key)
            layer[key]=round(float(v),2)
        if layer['end'] and layer['end']<=layer['start']+.05:raise ValueError('Lớp ảnh: thời điểm kết thúc phải sau thời điểm bắt đầu (0 = tới hết video).')
        for key in ('uid','name'):
            if isinstance(item.get(key),str) and len(item[key])<=120:layer[key]=item[key]
        out.append(layer)
    return out


def video_box(opts):
    if opts.get('units') == 'px':
        b={key:round(opts['video_'+key]) for key in ('x','y','width','height')}
        z=opts.get('video_zoom',100)/100
        return dict(x=round(b['x']+b['width']*(1-z)/2),y=round(b['y']+b['height']*(1-z)/2),width=max(1,round(b['width']*z)),height=max(1,round(b['height']*z)))
    zoom = opts['zoom']/100
    w,h = round(720*zoom/2)*2,round(1280*zoom/2)*2
    return dict(width=w,height=h,x=round((720-w)/2+720*opts['video_x']/100),
                y=round((1280-h)/2+1280*opts['video_y']/100))


def frame_box(opts):
    if opts.get('units') == 'px':
        return {key:round(opts['frame_'+key]) for key in ('x','y','width','height')}
    w=round(W*opts['frame_width']/100)
    h=round(H*opts['frame_height']/100)
    x=round(max(0,min(W-w,W*opts['frame_x']/100-w/2)))
    y=round(min(H-h,H*opts['frame_y']/100))
    return dict(x=x,y=y,width=w,height=h)


CASES=('none','upper','lower','title')


def letter_case(text,case):
    """Chữ hoa / chữ thường / Viết Hoa Đầu Từ, like CapCut (the text typed or written by the AI is kept as it is)."""
    if case=='upper':return text.upper()
    if case=='lower':return text.lower()
    if case=='title':return ' '.join(w[:1].upper()+w[1:].lower() for w in text.split(' '))
    return text


def layout(opts,strict=True):
    result=[]
    for key in TEXT_KEYS:
        text=opts.get(key,'')
        if not isinstance(text,str) or not text.strip():continue
        text=letter_case(text,opts.get(key+'_case','none'))
        font,size=opts[key+'_font'],opts[key+'_size']
        spacing=opts.get(key+'_word',0) or 0   # extra design px between words
        letter=opts.get(key+'_letter',0) or 0   # extra design px between letters (CapCut "Ký tự")
        wide=lambda s:width(s,font,size)+letter*max(0,len(s)-1)
        px=opts.get('units')=='px'
        box_width=round(opts[key+'_width'] if px else W*opts[key+'_width']/100)
        lines=[];paragraph_ends=[]
        for paragraph in text.split('\n'):
            wrapped=wrap(paragraph,font,size,box_width-2*opts[key+'_outline']-4,spacing,letter)
            lines.extend(wrapped);paragraph_ends.extend([False]*(len(wrapped)-1)+[True])
        step=size+opts[key+'_gap'];natural=len(lines)*step
        height=opts.get(key+'_height',0) or natural
        vertical=opts.get(key+'_valign','top')
        text_offset=max(0,height-natural)*{'top':0,'middle':.5,'bottom':1}[vertical]
        y=round(opts[key+'_y'] if px else H*opts[key+'_y']/100)
        x=round(opts[key+'_x'] if px else max(2,min(W-box_width-2,W*opts[key+'_x']/100-box_width/2)))
        problems=[]
        if len(lines)>40 or y+text_offset+natural>H-4:problems.append('Chữ vượt chiều cao canvas. Kéo lên hoặc giảm cỡ chữ.')
        if x+box_width>W:problems.append('Hộp chữ vượt cạnh phải. Giảm X hoặc độ rộng.')
        if natural>height+.01:problems.append('Chữ tràn chiều cao hộp. Tăng H, giảm font hoặc đặt H=0 tự động.')
        if strict and problems:raise ValueError(TEXT_LABELS[key]+': '+problems[0])
        offsets=[];line_runs=[]
        for li,line in enumerate(lines):
            factor={'left':0,'center':.5,'right':1,'justify':0}[opts[key+'_align']]
            words=line.split()
            line_width=wide(line)+spacing*max(0,len(words)-1)
            at=round(x+(box_width-line_width)*factor,2);offsets.append(at)
            justify=opts[key+'_align']=='justify' and not paragraph_ends[li] and len(words)>1
            if not (spacing or letter or justify):
                line_runs.append([dict(text=line,x=at)]);continue
            # one run per word (word spacing, justify) or per letter (letter spacing): same positions in preview and export
            gap=(box_width-sum(wide(w) for w in words))/(len(words)-1) if justify else width(' ',font,size)+2*letter+spacing
            runs=[];pos=x if justify else at
            for word in words:
                if letter:
                    p=pos
                    for c in word:
                        runs.append(dict(text=c,x=round(p,3)));p+=width(c,font,size)+letter
                else:runs.append(dict(text=word,x=round(pos,3)))
                pos+=wide(word)+gap
            line_runs.append(runs)
        result.append(dict(key=key,text='\n'.join(lines),lines=lines,line_x=offsets,line_runs=line_runs,
                           x=x,y=y,width=box_width,height=height,text_offset=text_offset,content_y=y+text_offset,valign=vertical,natural_height=natural,size=size,gap=opts[key+'_gap'],
                           font=font,family=FONTS[font][1],align=opts[key+'_align'],color=opts[key+'_color'],
                           outline=opts[key+'_outline'],outline_color=opts[key+'_outline_color'],warnings=problems,opacity=opts.get(key+'_opacity',100),
                           start=opts.get(key+'_start',0),end=opts.get(key+'_end',0),box=text_box(opts,key,x,y+text_offset,box_width,natural)))
    return result


def text_box(opts,key,x,y,width,height):
    """Optional filled (rounded) box behind a caption, in 720x1280 design pixels."""
    if opts.get(key+'_box','none')!='solid':return None
    pad=opts.get(key+'_box_pad',14)
    return dict(x=round(x-pad),y=round(y-pad*.6),width=round(width+2*pad),height=round(height+pad*1.2),
                radius=opts.get(key+'_box_radius',12),color=opts.get(key+'_box_color','#000000'),opacity=opts.get(key+'_box_opacity',70))


def box_png(width,height,radius,color,opacity):
    """Small RGBA PNG of a rounded rectangle; rows are assembled from runs so 4K boxes stay fast."""
    width,height=max(1,round(width)),max(1,round(height));radius=max(0,min(round(radius),width//2,height//2))
    rgba=bytes.fromhex(color[1:])+bytes([round(255*opacity/100)]);clear=b'\0\0\0\0'
    rows=[]
    for y in range(height):
        edge=max(radius-y-.5,y-(height-radius)+.5,0)
        inset=round(radius-math.sqrt(max(0,radius*radius-edge*edge))) if edge else 0
        rows.append(b'\0'+clear*inset+rgba*(width-2*inset)+clear*inset)
    def chunk(kind,data):
        return struct.pack('!I',len(data))+kind+data+struct.pack('!I',zlib.crc32(kind+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',width,height,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(rows),6))+chunk(b'IEND',b'')


def artwork(opts):
    color=tuple(bytes.fromhex(opts['color'][1:]))
    other=tuple(bytes.fromhex(opts['color2'][1:])) if opts['background']=='gradient' else color
    start=opts['fade_start'] if opts.get('units')=='px' else H*opts['fade_start']/100
    height=opts['fade_height'] if opts.get('units')=='px' else H*opts['fade_height']/100
    pixels=[]
    for y in range(H):
        t=min(1,max(0,(y-start)/height))
        mix=min(1,max(0,(y-start)/max(1,H-start)))
        rgb=bytes(round(a+(b-a)*mix) for a,b in zip(color,other))
        # background 'none': no colour layer or fade, the video shows on black where it does not cover
        alpha=0 if opts['background']=='none' else round(255*opts['opacity']/100*t*t*(3-2*t))
        pixels.append(bytearray((rgb+bytes([alpha]))*W))

    original = [bytes(row) for row in pixels] if 0 < opts['frame_opacity'] < 100 else None

    def span(y,x1,x2,rgba):
        if not 0<=y<H:
            return
        row=pixels[y]
        r,g,b,a=rgba
        x1,x2=max(0,x1),min(W,x2)
        if x2<=x1:
            return
        # fast paths (same result): an opaque fill, or a fill over fully transparent pixels, is a plain copy
        if a==255 or not any(row[4*x1+3:4*x2:4]):
            row[4*x1:4*x2]=bytes((r,g,b,a))*(x2-x1)
            return
        a0=a/255
        for x in range(x1,x2):
            i=4*x
            old=row[i+3]/255
            combined=a0+old*(1-a0)
            if combined:
                row[i:i+4]=bytes((round((r*a0+row[i]*old*(1-a0))/combined),
                                  round((g*a0+row[i+1]*old*(1-a0))/combined),
                                  round((b*a0+row[i+2]*old*(1-a0))/combined),round(combined*255)))

    def rounded(x,y,w,h,radius,fill):
        x,y,w,h,radius=map(round,(x,y,w,h,min(radius,w/2,h/2)))
        for yy in range(max(0,y),min(H,y+h)):
            edge=max(radius-(yy-y)-.5,(yy-(y+h-radius))+.5,0)
            inset=radius-math.sqrt(max(0,radius*radius-edge*edge)) if edge else 0
            span(yy,math.ceil(x+inset),math.floor(x+w-inset),fill(yy-y) if callable(fill) else fill)

    box=frame_box(opts)
    x,y,w,h=[box[k] for k in ('x','y','width','height')]
    fill=tuple(bytes.fromhex(opts['frame_color'][1:]))
    border=tuple(bytes.fromhex(opts['border_color'][1:]))
    style=opts['frame_style']
    r=min(40,h*.12)
    if style not in ('none','custom') and opts['frame_opacity'] > 0:
        if style=='pink':
            rounded(x,y+6,w,h-6,r,(*border,255))
            rounded(x+6,y,w-12,h-12,r,(*border,255))
            rounded(x+12,y+6,w-24,h-24,r-5,(*fill,255))
            rounded(x+17,y+11,w-34,h-34,r-8,
                    lambda yy: tuple(round(c+(255-c)*max(0,1-yy/max(1,h*.35))*opts['gloss']/180) for c in fill)+(255,))
            for cx,cy,size in [(x+8,y+8,18),(x+w-8,y+12,20),(x+8,y+h-12,15),(x+w-8,y+h-16,15)]:
                for dy in range(-size,size+1):
                    half=max(1,round((1-abs(dy)/size)**2*size*.45))
                    span(cy+dy,cx-half,cx+half+1,(*border,255))
        elif style=='glass':
            rounded(x,y,w,h,r,(*border,200))
            rounded(x+2,y+2,w-4,h-4,r-2,(*fill,125))
            rounded(x+9,y+7,w-18,h*.22,r/2,(255,255,255,40))
        elif style=='gold':
            rounded(x,y,w,h,r,(*border,255))
            rounded(x+4,y+4,w-8,h-8,r-2,(*fill,255))
            rounded(x+10,y+10,w-20,h-20,r-5,(*border,255))
            rounded(x+12,y+12,w-24,h-24,r-7,(*fill,255))
        elif style=='minimal':
            rounded(x,y,w,h,r*.6,(*fill,245))
            rounded(x,y+16,5,h-32,2,(*border,255))
        elif style=='neon':
            for spread,alpha in [(10,15),(7,25),(4,50)]:
                rounded(x-spread,y-spread,w+2*spread,h+2*spread,r+spread,(*border,alpha))
            rounded(x,y,w,h,r,(*border,255))
            rounded(x+3,y+3,w-6,h-6,r-3,(*fill,250))
        elif style=='ribbon':
            rounded(x,y,w,h,5,(*border,255))
            rounded(x+3,y+3,w-6,h-6,4,(*fill,255))
            rounded(x+12,y+12,w-24,7,3,(*border,220))
            rounded(x+12,y+h-19,w-24,7,3,(*border,220))
    if original is not None and style not in ('none','custom'):
        factor = opts['frame_opacity']/100
        for yy in range(max(0,y-30),min(H,y+h+30)):
            before,after = original[yy],pixels[yy]
            for xx in range(max(0,x-30),min(W,x+w+30)):
                at = xx*4
                a,b = before[at+3]/255,after[at+3]/255
                alpha = a*(1-factor)+b*factor
                if alpha:
                    for c in range(3):
                        after[at+c] = round((before[at+c]*a*(1-factor)+after[at+c]*b*factor)/alpha)
                    after[at+3] = round(alpha*255)
    raw=b''.join(b'\0'+row for row in pixels)
    def chunk(kind,data):
        return struct.pack('!I',len(data))+kind+data+struct.pack('!I',zlib.crc32(kind+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',W,H,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(raw,6))+chunk(b'IEND',b'')


# Reuse graphics when only text/timeline changes. Cache keys contain no source text or keys.
from functools import lru_cache

@lru_cache(maxsize=32)
def _graphic_layer(values,frame):
    opts=settings(dict(values))
    if frame:opts['opacity']=0
    else:opts['frame_style']='none'
    return artwork(opts)


def artwork_layers(opts):
    bg=('units','color','color2','background','fade_start','fade_height','opacity')
    fr=('units','frame_style','frame_x','frame_y','frame_width','frame_height','frame_color','border_color','frame_opacity','gloss')
    background=_graphic_layer(tuple((k,opts[k]) for k in bg),False)
    values={k:opts[k] for k in fr}
    if values['frame_style']=='custom':values['frame_style']='none'
    frame=_graphic_layer(tuple(values.items()),True)
    return background,frame
