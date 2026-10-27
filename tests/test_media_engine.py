import math
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path
from design import settings,layout
from media_engine import plan,tempo,probe,build,RESOLUTIONS

ROOT=Path(__file__).resolve().parents[1]


class TimingTests(unittest.TestCase):
    def test_trim_retime_offset_and_length_policies(self):
        video=dict(duration=10,has_audio=True);audio=dict(duration=12,has_audio=True)
        opts=dict(video_start=2,video_end=8,video_speed=2,audio_start=1,audio_end=9,audio_speed=2,audio_offset=.5,audio_mode='replace')
        self.assertEqual(plan({**opts,'duration_policy':'audio'},video,audio)['duration'],4.5)
        self.assertEqual(plan({**opts,'duration_policy':'video'},video,audio)['duration'],3)
        self.assertEqual(plan({**opts,'duration_policy':'shortest'},video,audio)['duration'],3)
        with self.assertRaises(ValueError):plan({**opts,'video_end':1},video,audio)
        with self.assertRaises(ValueError):plan({**opts,'audio_speed':0},video,audio)
        self.assertEqual(tempo(.25),'atempo=0.5,atempo=0.500000000')
        self.assertIn('atempo=2',tempo(4))

    def test_justify_spans_fill_nonfinal_line(self):
        opts=settings(dict(units='px',title='',body='Một đoạn nội dung tiếng Việt để thử căn đều hai bên với nhiều từ và nhiều dòng.',body_align='justify',body_width=230,body_x=90,body_y=400))
        item=layout(opts)[0]
        self.assertGreater(len(item['line_runs'][0]),1)
        from fonts import width
        first=item['line_runs'][0];last=first[-1]
        self.assertAlmostEqual(first[0]['x'],90,places=2)
        self.assertAlmostEqual(last['x']+width(last['text'],item['font'],item['size']),90+230,places=2)
        self.assertEqual(len(item['line_runs'][-1]),1)
        bad={**opts,'body_height':10}
        self.assertTrue(layout(bad,strict=False)[0]['warnings'])
        with self.assertRaises(ValueError):layout(bad)


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg/FFprobe required')
class NativeRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT/'.local').mkdir(exist_ok=True)
        cls.tmp=tempfile.TemporaryDirectory(prefix='render-test-',dir=ROOT/'.local');cls.folder=Path(cls.tmp.name)
        cls.video=cls.folder/'input.mp4';cls.audio=cls.folder/'voice.wav'
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=s=180x320:r=30:d=3','-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=3','-c:v','libx264','-threads','2','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(cls.video)],check=True)
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=880:sample_rate=48000:duration=4',str(cls.audio)],check=True)
        cls.vi,cls.ai=probe(cls.video),probe(cls.audio)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def render(self,**values):
        opts=settings(dict(units='px',title='THỬ',body='Một đoạn nội dung để kiểm tra căn đều hai bên trong khung chữ.',body_align='justify',body_width=300,body_x=100,**values))
        cmd,p=build(self.folder,opts,self.video,self.vi,self.audio,self.ai)
        result=subprocess.run(cmd,cwd=self.folder,capture_output=True,text=True,timeout=180)
        self.assertEqual(result.returncode,0,result.stderr[-2000:])
        return p,probe(self.folder/'review.mp4')

    def test_trim_rotation_audio_replacement_pitch_and_volume(self):
        options=dict(video_start=.2,video_end=2.6,video_speed=1.2,video_rotation=17,video_zoom=85,audio_start=.4,audio_end=3.4,audio_speed=1.5,audio_offset=.5,audio_mode='replace',duration_policy='audio')
        p,actual=self.render(**options,audio_volume=100)
        self.assertAlmostEqual(p['duration'],2.5,places=4)
        self.assertAlmostEqual(actual['duration'],2.5,delta=.12)
        self.assertTrue(actual['has_audio'])
        def samples():
            raw=subprocess.check_output(['ffmpeg','-v','error','-ss','0.8','-t','0.5','-i',str(self.folder/'review.mp4'),'-vn','-ac','1','-ar','48000','-f','f32le','-'])
            return struct.unpack('<'+'f'*(len(raw)//4),raw)
        full=samples();rms=lambda data:math.sqrt(sum(x*x for x in data)/len(data))
        crossings=sum(a<=0<b for a,b in zip(full,full[1:]))/.5
        self.assertAlmostEqual(crossings,880,delta=35) # atempo preserves pitch, replacement is not original 440Hz
        self.render(**options,audio_volume=50)
        self.assertAlmostEqual(rms(samples())/rms(full),.5,delta=.08)

    def test_native_output_dimensions_all_presets(self):
        for resolution,size in RESOLUTIONS.items():
            with self.subTest(resolution=resolution):
                _,actual=self.render(video_end=.15,audio_mode='original',resolution=resolution)
                self.assertEqual((actual['width'],actual['height']),size)
                self.assertLess(actual['duration'],.4)


if __name__=='__main__':unittest.main()
