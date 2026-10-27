"""Bounded, local-only thumbnails and waveform previews; no external uploads."""
import array
import base64
import json
import math
import subprocess
import threading
from pathlib import Path
from media_engine import probe

LOCK=threading.Lock()

def analyze(source,cache,kind):
    source,cache=Path(source),Path(cache)
    with LOCK:
        if cache.is_file():
            try:return json.loads(cache.read_text())
            except (ValueError,OSError):pass
        meta=probe(source);duration=meta['duration']
        result=dict(duration=duration,thumbnails=[],peaks=[],note='')
        if kind=='video':
            for index in range(10):
                at=max(0,min(duration-.1,duration*index/10))
                run=subprocess.run(['ffmpeg','-v','error','-nostdin','-threads','1','-ss',str(at),'-i',str(source),'-frames:v','1','-vf','scale=96:54:force_original_aspect_ratio=increase,crop=96:54','-threads','1','-f','image2pipe','-c:v','mjpeg','-'],capture_output=True,timeout=15)
                if run.returncode==0 and run.stdout:result['thumbnails'].append('data:image/jpeg;base64,'+base64.b64encode(run.stdout).decode())
        if meta['has_audio'] and duration<=7200:
            run=subprocess.run(['ffmpeg','-v','error','-nostdin','-threads','1','-i',str(source),'-vn','-ac','1','-ar','1000','-f','s16le','-'],capture_output=True,timeout=90,check=True)
            samples=array.array('h');samples.frombytes(run.stdout)
            stride=max(1,math.ceil(len(samples)/600))
            result['peaks']=[round(max((abs(v) for v in samples[i:i+stride]),default=0)/32768,4) for i in range(0,len(samples),stride)]
        elif duration>7200:result['note']='Nguồn trên 2 giờ: không tạo sóng âm; vẫn cắt bằng số.'
        cache.parent.mkdir(exist_ok=True)
        cache.write_text(json.dumps(result),encoding='utf-8')
        return result
