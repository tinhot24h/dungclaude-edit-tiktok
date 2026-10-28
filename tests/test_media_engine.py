import math
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path
from design import settings,layout
from media_engine import plan,tempo,probe,build,keep,RESOLUTIONS
from design import box_png,image_layers

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

    def test_cuts_music_and_preview_plan(self):
        video=dict(duration=10,has_audio=True);music=dict(duration=3,has_audio=True)
        self.assertEqual(keep([[2,3],[2.5,4],[9,12]],1,10),[(1,2),(4,9)])
        p=plan(dict(video_start=1,video_end=10,video_speed=2,video_cuts=[[2,4]]),video)
        self.assertEqual(p['duration'],3.5)
        with self.assertRaises(ValueError):plan(dict(video_cuts=[[0,10]]),video)
        with self.assertRaises(ValueError):plan(dict(video_cuts=[[3,2]]),video)
        with self.assertRaises(ValueError):plan(dict(video_cuts='x'),video)
        p=plan(dict(music_volume=50,preview_at=8),video,None,music)
        self.assertEqual((p['music']['volume'],p['preview_at'],p['output_duration']),(50,8,2))
        with self.assertRaises(ValueError):plan(dict(fps=24),video)
        with self.assertRaises(ValueError):plan(dict(encoder='libx265'),video)
        with self.assertRaises(ValueError):plan(dict(music_loop='yes'),video,None,music)

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

    def test_cuts_music_motion_loudness_and_60fps(self):
        options=dict(video_end=3,video_cuts=[[.5,1.5]],audio_mode='original',fps=60,video_motion='zoom_in',motion_amount=20,
                     loudness='tiktok',music_volume=40,music_fade_in=.3,music_fade_out=.3)
        opts=settings(dict(units='px',title='THỬ',body='',**options))
        cmd,p=build(self.folder,opts,self.video,self.vi,None,None,None,self.audio,self.ai)
        result=subprocess.run(cmd,cwd=self.folder,capture_output=True,text=True,timeout=180)
        self.assertEqual(result.returncode,0,result.stderr[-2000:])
        actual=probe(self.folder/'review.mp4')
        self.assertAlmostEqual(actual['duration'],2,delta=.12)
        rate=subprocess.check_output(['ffprobe','-v','error','-select_streams','v','-show_entries','stream=r_frame_rate','-of','csv=p=0',str(self.folder/'review.mp4')],text=True).strip()
        self.assertEqual(rate,'60/1')

    def test_reordered_pieces_play_in_the_given_order(self):
        opts=settings(dict(units='px',title='',body='',audio_mode='original',video_segments=[[2,2.5],[0,1]]))
        cmd,p=build(self.folder,opts,self.video,self.vi)
        self.assertEqual(p['video_segments'],[(2,2.5,1),(0,1,1)])
        result=subprocess.run(cmd,cwd=self.folder,capture_output=True,text=True,timeout=180)
        self.assertEqual(result.returncode,0,result.stderr[-2000:])
        self.assertAlmostEqual(probe(self.folder/'review.mp4')['duration'],1.5,delta=.12)
        # testsrc2 draws a running timestamp, so frame brightness differs; compare the first frame with source t=2s
        def frame(path,at):return subprocess.check_output(['ffmpeg','-v','error','-ss',str(at),'-i',str(path),'-frames:v','1','-vf','scale=16:28,format=gray','-f','rawvideo','-'])
        out=frame(self.folder/'review.mp4',0)
        diff=lambda x,y:sum(abs(a-b) for a,b in zip(x,y))
        self.assertLess(diff(out,frame(self.video,2)),diff(out,frame(self.video,0)))
        with self.assertRaises(ValueError):plan(dict(video_segments=[[1,1.01]]),self.vi)
        with self.assertRaises(ValueError):plan(dict(video_segments=[[0,1]]*61),self.vi)

    def test_each_piece_has_its_own_speed(self):
        self.assertAlmostEqual(plan(dict(video_segments=[[0,1,2],[1,3,.5]],video_speed=1),self.vi)['duration'],4.5)
        self.assertAlmostEqual(plan(dict(video_segments=[[0,1,2],[1,3]],video_speed=2),self.vi)['duration'],1.25)
        with self.assertRaises(ValueError):plan(dict(video_segments=[[0,1,5]]),self.vi)
        with self.assertRaises(ValueError):plan(dict(video_segments=[[0,1,True]]),self.vi)
        opts=settings(dict(units='px',title='',body='',audio_mode='original',video_segments=[[0,1,2],[1,2,.5]]))
        cmd,p=build(self.folder,opts,self.video,self.vi)
        self.assertAlmostEqual(p['duration'],2.5)
        graph=(self.folder/'render.ffgraph').read_text()
        self.assertIn('setpts=(PTS-STARTPTS)/2.000000000',graph);self.assertIn('atempo=2.000000000',graph);self.assertIn('atempo=0.500000000',graph)
        result=subprocess.run(cmd,cwd=self.folder,capture_output=True,text=True,timeout=180)
        self.assertEqual(result.returncode,0,result.stderr[-2000:])
        self.assertAlmostEqual(probe(self.folder/'review.mp4')['duration'],2.5,delta=.12)

    def test_image_layer_is_drawn_in_its_window(self):
        images=self.folder/'images';images.mkdir(exist_ok=True);key='ab'*16
        (images/(key+'.png')).write_bytes(box_png(40,40,0,'#ff0000',100))
        layer=dict(id=key,x=100,y=200,width=200,height=200,opacity=100,start=0,end=1,rotation=0)
        opts=settings(dict(units='px',title='',body='',background='none',frame_style='none',audio_mode='original',video_end=2,images=[layer]))
        cmd,p=build(self.folder,opts,self.video,self.vi,images_dir=images)
        self.assertIn("enable='between(t,0.0,1.0)'",(self.folder/'render.ffgraph').read_text())
        result=subprocess.run(cmd,cwd=self.folder,capture_output=True,text=True,timeout=180)
        self.assertEqual(result.returncode,0,result.stderr[-2000:])
        def pixel(at):
            raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(at),'-i',str(self.folder/'review.mp4'),'-frames:v','1','-vf','crop=2:2:200:300,format=rgb24','-f','rawvideo','-'])
            return raw[0],raw[1],raw[2]
        r,g,b=pixel(.5);self.assertTrue(r>200 and g<60 and b<60,(r,g,b))
        r,g,b=pixel(1.5);self.assertFalse(r>200 and g<60 and b<60,(r,g,b))
        with self.assertRaises(ValueError):build(self.folder,opts,self.video,self.vi,images_dir=self.folder/'missing')

    def test_flip_and_music_speed(self):
        opts=settings(dict(units='px',title='',body='',audio_mode='original',video_end=1,video_flip='h'))
        build(self.folder,opts,self.video,self.vi)
        self.assertIn('hflip,rotate',(self.folder/'render.ffgraph').read_text())
        with self.assertRaises(ValueError):settings(dict(units='px',video_flip='x'))
        music=dict(duration=3,has_audio=True)
        self.assertEqual(plan(dict(music_speed=1.5),self.vi,None,music)['music']['speed'],1.5)
        with self.assertRaises(ValueError):plan(dict(music_speed=3),self.vi,None,music)
        cmd,_=build(self.folder,settings(dict(units='px',title='',body='',audio_mode='original',video_end=1,music_speed=1.5)),self.video,self.vi,music_path=self.audio,music=probe(self.audio))
        self.assertIn('atempo=1.500000000',(self.folder/'render.ffgraph').read_text())
        result=subprocess.run(cmd,cwd=self.folder,capture_output=True,text=True,timeout=180)
        self.assertEqual(result.returncode,0,result.stderr[-2000:])

    def test_image_layer_validation(self):
        key='cd'*16
        self.assertEqual(image_layers([dict(id=key,width=50,height=60)])[0]['opacity'],100)
        for bad in ([dict(id='x',width=50,height=60)],[dict(id=key,width=1,height=60)],[dict(id=key,width=50,height=60,start=2,end=1)],[dict(id=key,width=50,height=60)]*13,'x'):
            with self.assertRaises(ValueError):image_layers(bad)

    def test_timed_text_layers(self):
        opts=settings(dict(units='px',title='TIÊU ĐỀ',body='',text1='Chữ thêm',text1_start=.5,text1_end=1.5,title_start=0,title_end=0,audio_mode='original',video_end=2))
        items={i['key']:i for i in layout(opts)}
        self.assertEqual((items['text1']['start'],items['text1']['end']),(.5,1.5))
        cmd,p=build(self.folder,opts,self.video,self.vi)
        graph=(self.folder/'render.ffgraph').read_text()
        self.assertIn("enable='between(t,0.5,1.5)'",graph)
        self.assertEqual(graph.count('enable='),graph.count('text1-'))
        result=subprocess.run(cmd,cwd=self.folder,capture_output=True,text=True,timeout=180)
        self.assertEqual(result.returncode,0,result.stderr[-2000:])
        with self.assertRaises(ValueError):settings(dict(units='px',text2_start=3,text2_end=2))

    def test_background_off_uses_black_base(self):
        opts=settings(dict(units='px',title='',body='',background='none',color='#ff00ff',audio_mode='original',video_end=.2))
        build(self.folder,opts,self.video,self.vi)
        graph=(self.folder/'render.ffgraph').read_text()
        self.assertIn('color=c=0x000000',graph);self.assertNotIn('0xff00ff',graph)

    def test_ducked_music_and_preview_window(self):
        options=dict(audio_mode='replace',audio_end=2,duration_policy='video',music_duck=True,preview_at=1)
        opts=settings(dict(units='px',title='',body='',**options))
        cmd,p=build(self.folder,opts,self.video,self.vi,self.audio,self.ai,None,self.audio,self.ai)
        self.assertIn('sidechaincompress',(self.folder/'render.ffgraph').read_text())
        result=subprocess.run(cmd,cwd=self.folder,capture_output=True,text=True,timeout=180)
        self.assertEqual(result.returncode,0,result.stderr[-2000:])
        self.assertEqual(p['output'],'preview.mp4')
        self.assertAlmostEqual(probe(self.folder/'preview.mp4')['duration'],2,delta=.12)

    def test_native_output_dimensions_all_presets(self):
        for resolution,size in RESOLUTIONS.items():
            with self.subTest(resolution=resolution):
                _,actual=self.render(video_end=.15,audio_mode='original',resolution=resolution)
                self.assertEqual((actual['width'],actual['height']),size)
                self.assertLess(actual['duration'],.4)


if __name__=='__main__':unittest.main()
