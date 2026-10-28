import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
import wave
from pathlib import Path
from unittest import mock
import dubbing
import media_engine


def tone(path,seconds,freq=440):
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'sine=frequency={freq}:duration={seconds}','-c:a','libmp3lame',str(path)],check=True)


class HelperTests(unittest.TestCase):
    def test_balance_splits_the_speed_between_voice_and_video(self):
        lo,hi,fast,slow=.98,1.1,1/1.2,1/.85
        t,v=dubbing.balance(10.8,10,lo,hi,fast,slow)              # 8% longer voice: ~4% each instead of 8% on one side
        self.assertAlmostEqual(t,1.0392,places=3);self.assertAlmostEqual(v,1.0392,places=3);self.assertAlmostEqual(10.8/t,10*v,places=6)
        t,v=dubbing.balance(20,10,lo,hi,fast,slow)                # far too long: both at their limits, the rest is cut
        self.assertEqual((t,round(v,4)),(1.1,round(slow,4)))
        t,v=dubbing.balance(7,10,lo,hi,fast,slow)                 # shorter voice: 0.98× and the video 1.2× faster
        self.assertEqual((t,round(v,4)),(.98,round(fast,4)))
        t,v=dubbing.balance(9.6,10,lo,hi,fast,slow)               # voice can only slow 2%: the video takes the rest
        self.assertEqual(t,.98);self.assertAlmostEqual(9.6/t,10*v,places=6)
        self.assertEqual(dubbing.balance(7,10,lo,hi,fast,slow,shorten=False),(1.0,1.0))   # keep the whole video
        self.assertEqual(dubbing.balance(10.05,10,lo,hi,fast,slow),(1.0,1.0))

    def test_srt_round_trip_and_limits(self):
        rows=dubbing.parse_srt('1\r\n00:00:01,000 --> 00:00:02,500\r\n你好\r\n世界\r\n\r\n2\n00:00:03.2 --> 00:00:04,000\n谢谢\n')
        self.assertEqual(rows,[dict(start=1.0,end=2.5,zh='你好 世界'),dict(start=3.2,end=4.0,zh='谢谢')])
        rows[0]['vi']='Xin chào';self.assertIn('00:00:01,000 --> 00:00:02,500\nXin chào',dubbing.to_srt(rows,'vi'))
        with self.assertRaises(dubbing.DubError):dubbing.parse_srt('không phải srt')
        self.assertEqual(dubbing.syllables('Xin chào, các bạn!'),4)
        self.assertEqual(dubbing.budget(dict(start=0,end=2),4.2),8)

    def test_grouping_and_fitting(self):
        segs=[dict(start=0,end=1,vi='Xin chào'),dict(start=1.1,end=2,vi='các bạn.'),dict(start=2.1,end=3,vi='Hôm nay'),dict(start=5,end=6,vi=''),dict(start=6,end=7,vi='Hết')]
        groups=dubbing.group_segments(segs)
        self.assertEqual([g['text'] for g in groups],['Xin chào các bạn.','Hôm nay','Hết'])
        self.assertEqual(groups[0]['lines'],[0,1])
        for g,sec in zip(groups,(1.5,6,1)):g['clip_seconds']=sec
        warnings=dubbing.fit(groups,8,1.3)
        self.assertEqual(groups[0]['tempo'],1.0)
        self.assertEqual(groups[1]['tempo'],1.3);self.assertGreater(groups[1]['overflow'],0);self.assertEqual(len(warnings),1)

    def test_options_validation(self):
        self.assertEqual(dubbing.options({})['background'],'duck')
        for bad in (dict(rate=10),dict(background='x'),dict(voice_id='abc'),dict(review='yes'),dict(model='a b')):
            with self.assertRaises(dubbing.DubError,msg=bad):dubbing.options(bad)


class PipelineBase(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name)
        self.data=root/'data';self.audio=root/'audio';self.out=root/'out';self.data.mkdir();self.audio.mkdir()
        self.settings=root/'settings.json';self.settings.write_text(json.dumps(dict(output_dir=str(self.out),auto_save=True)))
        self.vid='ab'*16;folder=self.data/self.vid;folder.mkdir()
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=s=180x320:r=30:d=4','-f','lavfi','-i','sine=frequency=300:duration=4','-ac','2',
                        '-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest','-f','mp4',str(folder/'source')],check=True)
        (folder/'source.json').write_text(json.dumps(dict(id=self.vid,name='clip.mp4',duration=4.0)))
        self.voice=root/'voice.mp3';tone(self.voice,2.2,700)
        self.store=dubbing.Store(self.data,self.settings,self.data,self.audio,media_engine.encoder_args)
        self.tasks={}
        def create(raw):
            k=f't{len(self.tasks)}';self.tasks[k]=raw['text'];return dict(task_id=k,state='submitted')
        self.patches=[mock.patch.object(dubbing,'transcribe_request',return_value=dict(segments=[dict(start=.2,end=1.4,text='你好'),dict(start=2.0,end=2.9,text='谢谢大家')])),
                      mock.patch.object(dubbing,'translate_request',side_effect=lambda key,model,lines,s:{l['id']:['Xin chào','Cảm ơn mọi người'][l['id']] for l in lines}),
                      mock.patch.object(dubbing.ai33_audio,'create_tts',side_effect=create),
                      mock.patch.object(dubbing.ai33_audio,'get_task',side_effect=lambda raw:dict(status='done',audio_url='https://cdn.example/a.mp3')),
                      mock.patch.object(dubbing.audio_files,'download',side_effect=lambda url,target:Path(target).write_bytes(self.voice.read_bytes())),
                      mock.patch.object(dubbing.time,'sleep',lambda s:None)]
        for p in self.patches:p.start()

    def tearDown(self):
        for p in self.patches:p.stop()
        self.tmp.cleanup()

    def job(self,**opts):
        key=uuid=None
        with mock.patch.object(self.store,'enqueue'):
            key=self.store.create(dict(video_ids=[self.vid],options=dict(voice_id='edge_vi-VN-HoaiMyNeural',**opts)))[0]
        return self.store.load(key)

class PipelineTests(PipelineBase):
    def test_review_pause_then_full_dub_with_soft_subtitles(self):
        job=self.job(subtitles='soft',background='duck',mode='lines',review=True)
        self.store.process(job,dict(openai='sk-test',ai33='k'),threading.Event())
        self.assertEqual(job['state'],'review');self.assertEqual([s['vi'] for s in job['segments']],['Xin chào','Cảm ơn mọi người'])
        self.assertTrue((self.data/'dub'/job['id']/'zh.srt').is_file())
        job['review_passed']=True;self.store.process(job,dict(openai='sk-test',ai33='k'),threading.Event())
        self.assertEqual(job['state'],'done',job['message'])
        self.assertTrue(all(v in ('done','skipped') for v in job['steps'].values()))
        self.assertEqual(list(self.tasks.values()),['Xin chào.\nCảm ơn mọi người.'])   # timestamp mode: ONE ai33 file
        out=self.data/'dub'/job['id']/'dubbed.mp4';info=dubbing.probe(out)
        self.assertAlmostEqual(info['duration'],4,delta=.15);self.assertIsNotNone(info['audio'])
        self.assertTrue(all(g.get('file') for g in job['groups']));self.assertAlmostEqual(sum(g['clip_seconds'] for g in job['groups']),2.2,delta=.05)
        saved=Path(job['outputs']['saved_path']);self.assertTrue(saved.is_file());self.assertTrue(saved.with_suffix('.srt').is_file())
        with wave.open(str(self.data/'dub'/job['id']/'voice.wav')) as w:self.assertAlmostEqual(w.getnframes()/w.getframerate(),4,delta=.01)
        # editing a line re-voices the file once (still one task)
        self.store.edit_lines(job['id'],[dict(i=1,vi='Cảm ơn')])
        self.store.process(job,dict(openai='sk-test',ai33='k'),threading.Event())
        self.assertEqual(job['state'],'done');self.assertEqual(list(self.tasks.values())[1:],['Xin chào.\nCảm ơn.'])

    def test_soft_subtitles_remove_background_and_editor_handoff(self):
        job=self.job(subtitles='soft',background='remove',review=False,mode='lines')
        self.store.process(job,dict(openai='sk-test',ai33='k'),threading.Event())
        self.assertEqual(job['state'],'done',job['message'])
        streams=subprocess.check_output(['ffprobe','-v','error','-show_entries','stream=codec_type','-of','csv=p=0',str(self.data/'dub'/job['id']/'dubbed.mp4')],text=True).split()
        self.assertEqual(sorted(streams),['audio','subtitle','video'])
        target=self.data/'new.mp4'
        result=self.store.to_editor(job['id'],lambda:target,lambda path,name:dict(asset_id='cd'*16,name=name))
        self.assertEqual(result['audio_asset_id'],'cd'*16);self.assertTrue(target.is_file())

    def test_srt_input_skips_recognition_and_keys_are_required(self):
        with mock.patch.object(self.store,'enqueue'):
            key=self.store.create(dict(video_ids=[self.vid],srt={self.vid:'1\n00:00:00,500 --> 00:00:01,500\n你好\n'},options=dict(voice_id='edge_vi-VN-HoaiMyNeural')))[0]
        job=self.store.load(key);self.assertEqual(job['steps']['asr'],'skipped')
        with mock.patch.dict('os.environ',{},clear=True):
            with self.assertRaises(dubbing.DubError):self.store.enqueue(key,{})
        self.assertNotIn('sk-',json.dumps(json.loads((self.data/'dub'/key/'job.json').read_text())))


if __name__=='__main__':
    unittest.main()


class ParagraphTests(PipelineBase):
    def test_one_paragraph_one_mp3_only_task_with_pause_timed_subtitles(self):
        # voice: 1.0s tone, 0.6s silence, 1.0s tone → the subtitle change lands in the pause
        voice=Path(self.tmp.name)/'speech.wav'
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=500:duration=1','-f','lavfi','-i','anullsrc=r=44100:cl=mono:d=0.6','-f','lavfi','-i','sine=frequency=500:duration=1',
                        '-filter_complex','[0][1][2]concat=n=3:v=0:a=1',str(voice)],check=True)
        sent=[];fetched=[]
        def download(url,target):fetched.append(url);Path(target).write_bytes(voice.read_bytes())
        with mock.patch.object(dubbing,'paragraph_request',return_value='Xin chào mọi người. Cảm ơn đã xem nha.') as para,\
             mock.patch.object(dubbing.ai33_audio,'create_tts',side_effect=lambda raw:sent.append(raw) or dict(task_id='p1',state='submitted')),\
             mock.patch.object(dubbing.ai33_audio,'get_task',return_value=dict(status='done',audio_url='https://cdn.example/a.mp3',srt_url='https://cdn.example/a.srt')),\
             mock.patch.object(dubbing.audio_files,'download',side_effect=download):
            job=self.job(subtitles='file',background='remove',review=True)
            self.store.process(job,dict(openai='sk',ai33='k'),threading.Event())
            self.assertEqual((job['state'],job['paragraph']),('review','Xin chào mọi người. Cảm ơn đã xem nha.'))
            self.assertEqual(para.call_args[0][4],int((4-.2)*4.2))
            job['review_passed']=True;self.store.process(job,dict(openai='sk',ai33='k'),threading.Event())
        self.assertEqual(job['state'],'done',job['message'])
        self.assertEqual(len(sent),1);self.assertNotIn('with_transcript',sent[0]);self.assertEqual(fetched,['https://cdn.example/a.mp3'])
        # 2.6 s voice on a 4 s video: both change a little (voice 0.98×, video 1.2×), the rest of the video is cut
        self.assertEqual((job['groups'][0]['tempo'],job['video_stretch']),(0.98,0.8333))
        self.assertAlmostEqual(job['output_duration'],.2*.8333+2.6/.98+.4,delta=.05)
        lines=job['vi_lines'];self.assertEqual([l['vi'] for l in lines],['Xin chào mọi người.','Cảm ơn đã xem nha.'])
        self.assertAlmostEqual(lines[1]['start'],.2*.8333+1.3/.98,delta=.15)
        self.assertIn('Xin chào mọi người.',(self.data/'dub'/job['id']/'vi.srt').read_text())
        # editing the paragraph re-voices it (one new task)
        self.store.edit_paragraph(job['id'],'Xin chào.')
        self.assertEqual((job['groups'],job['steps']['tts']),([],'pending'))

    def test_sentence_lines_snap_to_pauses(self):
        lines=dubbing.sentence_lines('Một hai ba. Bốn năm sáu bảy tám.',10,6,pauses=[2.6])
        self.assertEqual([(l['start'],l['end']) for l in lines],[(10,12.6),(12.6,16)])
        self.assertEqual(dubbing.sentence_lines('',0,3),[])

    def run_long(self,seconds,**opts):
        long=Path(self.tmp.name)/'long.mp3';tone(long,seconds,600)
        with mock.patch.object(dubbing,'paragraph_request',return_value='Một đoạn rất dài. Hai câu.'),\
             mock.patch.object(dubbing.ai33_audio,'get_task',return_value=dict(status='done',audio_url='https://cdn.example/a.mp3')),\
             mock.patch.object(dubbing.audio_files,'download',side_effect=lambda url,target:Path(target).write_bytes(long.read_bytes())):
            job=self.job(subtitles='file',background='duck',review=False,**opts)
            self.store.process(job,dict(openai='sk',ai33='k'),threading.Event())
        self.assertEqual(job['state'],'done',job['message'])
        self.assertAlmostEqual(dubbing.probe(self.data/'dub'/job['id']/'dubbed.mp4')['duration'],job['output_duration'],delta=.2)
        return job

    def test_slow_video_down_when_the_voice_is_longer(self):
        job=self.run_long(6,align='video',video_speed_min=.25)
        self.assertGreater(job['video_stretch'],1.5);self.assertEqual(len(job['vi_lines']),2)
        self.assertAlmostEqual(job['output_duration'],.2*job['video_stretch']+6+.3,delta=.1)

    def test_default_limits_then_cut_to_the_video(self):
        # video may slow to 0.85× at most; the rest of a 6 s voice in a 4 s video is cut where the video ends
        job=self.run_long(6,align='video')
        self.assertEqual(job['video_stretch'],round(1/.85,4));self.assertAlmostEqual(job['output_duration'],4/.85,delta=.02)
        self.assertGreater(job['groups'][0]['overflow'],1);self.assertTrue(any('cắt theo độ dài video' in w for w in job['warnings']))
        # auto: voice up to 1.1× first, then the video slows down for what is still missing
        job=self.run_long(4.4,align='auto')
        self.assertEqual(job['groups'][0]['tempo'],1.1);self.assertTrue(1<job['video_stretch']<=round(1/.85,4));self.assertEqual(job['groups'][0]['overflow'],0)

    def test_mp3_follows_video_both_ways(self):
        with mock.patch.object(dubbing,'paragraph_request',return_value='Ngắn.'):
            job=self.job(background='remove',review=False,align='voice',subtitles='none')
            self.store.process(job,dict(openai='sk',ai33='k'),threading.Event())
        # 2.2s voice in a 3.75s window is slowed down only to the floor of 0.98×
        self.assertEqual(job['state'],'done',job['message']);self.assertEqual(job['groups'][0]['tempo'],.98);self.assertEqual(job['video_stretch'],1)
        with self.assertRaises(dubbing.DubError):dubbing.options(dict(video_speed_max=.5))


class PromptTests(unittest.TestCase):
    def test_dub_uses_the_shared_template_and_the_strict_rule(self):
        import ai_translate
        seen={}
        def call(path,key,body,ctype,timeout=0):
            seen['body']=json.loads(body);return dict(status='completed',output=[dict(type='message',content=[dict(type='output_text',text='{"lines":[{"id":0,"vi":"Xin chào"}]}')])])
        with mock.patch.object(dubbing,'openai_call',side_effect=call):
            got=dubbing.translate_request('k','gpt-4.1-mini',[dict(id=0,zh='你好')],dubbing.options(dict(instructions='QUY TẮC RIÊNG: giọng hài hước')))
        rules=seen['body']['input'][0]['content']
        self.assertEqual(got,{0:'Xin chào'});self.assertIn('QUY TẮC RIÊNG: giọng hài hước',rules);self.assertIn(ai_translate.STRICT,rules)
        with mock.patch.object(dubbing,'openai_call',side_effect=call):
            dubbing.translate_request('k','m',[dict(id=0,zh='你好')],dubbing.options({}))
        self.assertIn('THƯƠNG HIỆU & THÔNG SỐ',seen['body']['input'][0]['content'])

    def test_sizes_and_volumes_are_flagged(self):
        import ai_translate
        out=ai_translate.check_fit(dict(script='Bình 500ml siêu tiện',title='',body='',hook=''),ai_translate.FIT_DEFAULTS)
        self.assertTrue(any('kích thước/thể tích' in w for w in out['warnings']))
        self.assertIsNone(ai_translate.SPEC.search('dùng 5 lần mỗi ngày'))
        self.assertIn(ai_translate.STRICT,ai_translate.system(dict(rules='x')))


class RecoveryTests(PipelineBase):
    def test_failed_task_lookup_falls_back_to_history_and_retries(self):
        calls=[]
        def get_task(raw):
            calls.append(1)
            raise dubbing.ai33_audio.AudioError('Dịch vụ ai33.pro đang gặp lỗi (HTTP 500).',502)
        found=iter([None,dict(status='done',audio_url='https://cdn.example/a.mp3',srt_url='')])
        with mock.patch.object(dubbing,'paragraph_request',return_value='Xin chào.'),mock.patch.object(dubbing.ai33_audio,'get_task',side_effect=get_task),\
             mock.patch.object(dubbing.ai33_audio,'find_task',side_effect=lambda raw,task:next(found)):
            job=self.job(background='remove',subtitles='none')
            self.store.process(job,dict(openai='sk',ai33='k'),threading.Event())
        self.assertEqual(job['state'],'done',job['message']);self.assertEqual(len(calls),2)

    def test_bad_key_still_stops(self):
        with mock.patch.object(dubbing,'paragraph_request',return_value='Xin chào.'),\
             mock.patch.object(dubbing.ai33_audio,'get_task',side_effect=dubbing.ai33_audio.AudioError('key sai',401)):
            job=self.job(background='remove',subtitles='none')
            with self.assertRaises(dubbing.ai33_audio.AudioError):self.store.process(job,dict(openai='sk',ai33='k'),threading.Event())

    def test_uploaded_mp3_skips_tts_and_exports(self):
        with mock.patch.object(dubbing,'paragraph_request',return_value='Xin chào.'),\
             mock.patch.object(dubbing.ai33_audio,'get_task',side_effect=dubbing.ai33_audio.AudioError('lỗi',502)),\
             mock.patch.object(dubbing.ai33_audio,'find_task',return_value=None),mock.patch.object(dubbing.Store,'poll',side_effect=dubbing.DubError('ai33 lỗi')):
            job=self.job(background='remove',subtitles='file')
            with self.assertRaises(dubbing.DubError):self.store.process(job,dict(openai='sk',ai33='k'),threading.Event())
        job['state']='error'
        with mock.patch.object(self.store,'enqueue') as queued:
            self.store.use_voice(job['id'],self.voice)
        queued.assert_called_once()
        self.assertEqual((job['steps']['tts'],job['groups'][0]['uploaded']),('done',True))
        self.store.process(job,{},threading.Event())
        self.assertEqual(job['state'],'done',job['message'])
        self.assertTrue((self.data/'dub'/job['id']/'dubbed.mp4').is_file())


class FrameOverlayTests(PipelineBase):
    def overlay(self,name,source_args):
        path=Path(self.tmp.name)/name;subprocess.run(['ffmpeg','-v','error','-y',*source_args,str(path)],check=True)
        return self.store.import_overlay(path,name)

    def test_frame_and_random_overlays_render(self):
        sparkle=self.overlay('sparkle.mp4',['-f','lavfi','-i','testsrc2=s=320x240:r=30:d=1.5','-pix_fmt','yuv420p'])
        logo=self.overlay('logo.png',['-f','lavfi','-i','color=c=red:s=64x64:d=0.04','-frames:v','1'])
        self.assertEqual((sparkle['still'],logo['still']),(False,True));self.assertEqual(len(self.store.overlays()),2)
        with mock.patch.object(dubbing,'paragraph_request',return_value='Xin chào.'):
            job=self.job(background='remove',review=False,subtitles='file',frame_canvas='9:16',frame_fit='blur',frame_zoom=120,frame_x=10,frame_rotate=8,frame_flip='h',
                         overlay=True,overlay_count=2,overlay_blend='screen',overlay_timing='random',overlay_opacity=50,end_with_voice=False)
            self.store.process(job,dict(openai='sk',ai33='k'),threading.Event())
        self.assertEqual(job['state'],'done',job['message'])
        self.assertEqual(sorted(o['id'] for o in job['overlays']),sorted([sparkle['id'],logo['id']]))
        out=self.data/'dub'/job['id']/'dubbed.mp4';info=dubbing.probe(out)
        self.assertEqual((info['video']['width'],info['video']['height']),(1080,1920));self.assertAlmostEqual(info['duration'],4,delta=.2)
        graph=(self.data/'dub'/job['id']/'export.ffgraph').read_text()
        for part in ('hflip','boxblur','rotate=','blend=all_mode=screen','tpad=start_duration'):self.assertIn(part,graph)
        self.assertNotIn('drawtext',graph)
        # normal blend + loop, re-export keeps the same random choice
        first=list(job['overlays'])
        job['options']=dubbing.options({**job['options'],'overlay_blend':'normal'});job['steps']['export']='pending'
        self.store.export(job,self.data/'dub'/job['id'],self.data/self.vid/'source',dubbing.probe(self.data/self.vid/'source'),threading.Event())
        self.assertEqual(job['overlays'],first);self.assertIn('colorchannelmixer=aa=0.500',(self.data/'dub'/job['id']/'export.ffgraph').read_text())
        self.store.delete_overlay(logo['id']);self.assertEqual(len(self.store.overlays()),1)
        with self.assertRaises(dubbing.DubError):self.store.import_overlay(Path(self.tmp.name)/'x.txt','x.txt')

    def test_transparent_mov_overlays_full_frame_with_its_alpha_and_gets_a_browser_preview(self):
        # ProRes 4444 with alpha: a red square on a fully transparent background, like effect packs exported from AE/CapCut
        mov=self.overlay('fx.mov',['-f','lavfi','-i',"color=black:s=320x320:r=30:d=1.5,format=rgba,geq=r='255':g='0':b='0':a='255*between(X,110,210)*between(Y,110,210)'",
                                   '-c:v','prores_ks','-profile:v','4444','-pix_fmt','yuva444p10le'])
        self.assertTrue(mov['alpha']);self.assertEqual(mov['codec'],'prores')
        preview=self.store.overlay_preview(mov);self.assertEqual(preview.name,mov['id']+'.preview.webm')
        self.assertEqual(dubbing.overlay_alpha(preview),(True,'vp9'))
        with mock.patch.object(dubbing,'paragraph_request',return_value='Xin chào.'):
            job=self.job(background='remove',review=False,subtitles='none',overlay=True,overlay_opacity=100,end_with_voice=False)  # default blend is screen
            self.store.process(job,dict(openai='sk',ai33='k'),threading.Event())
        self.assertEqual(job['state'],'done',job['message'])
        out=self.data/'dub'/job['id']/'dubbed.mp4';src=self.data/self.vid/'source'
        def pixel(path,x,y,t=3.2):
            return list(subprocess.run(['ffmpeg','-v','error','-ss',str(t),'-i',str(path),'-frames:v','1','-vf',f'crop=2:2:{x}:{y},scale=1:1','-f','rawvideo','-pix_fmt','rgb24','-'],capture_output=True).stdout)
        r,g,b=pixel(out,'iw/2','ih/2');self.assertGreater(r,200);self.assertLess(g+b,90)   # red on top, also after the 1.5 s clip looped
        corner,orig=pixel(out,4,4),pixel(src,4,4)
        self.assertTrue(all(abs(a-b)<25 for a,b in zip(corner,orig)),(corner,orig))   # transparent area leaves the video untouched
        self.assertNotIn('blend=all_mode=screen',(self.data/'dub'/job['id']/'export.ffgraph').read_text())

    def test_image_layer_position_size_and_blend(self):
        folder=self.data/self.vid
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=0x808080:s=180x320:r=30:d=4','-f','lavfi','-i','sine=d=4','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest','-f','mp4',str(folder/'source')],check=True)
        png=Path(self.tmp.name)/'box.png';subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=black:s=100x100','-frames:v','1',str(png)],check=True)
        img=self.store.import_image(png,'box.png');self.assertEqual((img['width'],img['height']),(100,100))
        def render(**opts):
            with mock.patch.object(dubbing,'paragraph_request',return_value='Xin chào.'):
                job=self.job(background='remove',review=False,subtitles='none',image=True,image_id=img['id'],**opts)
                self.store.process(job,dict(openai='sk',ai33='k'),threading.Event())
            self.assertEqual(job['state'],'done',job['message'])
            out=self.data/'dub'/job['id']/'dubbed.mp4'
            px=lambda x,y:list(subprocess.run(['ffmpeg','-v','error','-ss','1','-i',str(out),'-frames:v','1','-vf',f'crop=2:2:{x}:{y},scale=1:1','-f','rawvideo','-pix_fmt','rgb24','-'],capture_output=True).stdout)
            return px,job
        # black box, 50% of the width, top-left quarter (centre at x=-25%, y=-25%)
        px,job=render(image_w=50,image_x=-25,image_y=-25,end_with_voice=False)
        self.assertLess(sum(px(45,80)),40);self.assertGreater(sum(px(135,240)),300)
        # multiply with black → black; screen with black → unchanged grey; opacity 50% → half way
        px,_=render(image_w=100,image_h=100,image_blend='screen',end_with_voice=False);self.assertGreater(sum(px(90,160)),300)
        px,_=render(image_w=100,image_h=100,image_blend='multiply',end_with_voice=False);self.assertLess(sum(px(90,160)),40)
        px,_=render(image_w=100,image_h=100,image_opacity=50,end_with_voice=False);self.assertTrue(150<sum(px(90,160))<250)
        with self.assertRaises(dubbing.DubError):dubbing.options(dict(image_blend='x'))

    def test_video_is_cut_where_the_voice_ends(self):
        # 2.2 s voice from 0.2 s in a 4 s video → the video ends ~0.4 s after the last word
        with mock.patch.object(dubbing,'paragraph_request',return_value='Ngắn.'):
            job=self.job(background='remove',review=False,subtitles='none')
            self.store.process(job,dict(openai='sk',ai33='k'),threading.Event())
        self.assertEqual(job['state'],'done',job['message'])
        self.assertAlmostEqual(job['output_duration'],.2+2.2+.4,delta=.15)
        self.assertAlmostEqual(dubbing.probe(self.data/'dub'/job['id']/'dubbed.mp4')['duration'],job['output_duration'],delta=.15)

    def test_trim_start_and_end(self):
        with mock.patch.object(dubbing,'paragraph_request',return_value='Xin chào.'):
            job=self.job(background='remove',review=False,subtitles='none',trim_start=.5,trim_end=.5)
            self.store.process(job,dict(openai='sk',ai33='k'),threading.Event())
        self.assertEqual(job['state'],'done',job['message'])
        self.assertAlmostEqual(job['duration'],3,delta=.1)
        # the shorter voice speeds the trimmed video up (≤1.2×), then the rest is cut after the last word
        out=dubbing.probe(self.data/'dub'/job['id']/'dubbed.mp4')['duration']
        self.assertAlmostEqual(out,job['output_duration'],delta=.15);self.assertLessEqual(out,3.05)
        with self.assertRaises(dubbing.DubError):dubbing.options(dict(trim_start=-1))

    def test_overlay_is_optional_and_empty_library_does_not_block(self):
        with mock.patch.object(dubbing,'paragraph_request',return_value='Xin chào.'):
            job=self.job(background='remove',review=False,subtitles='none',overlay=True)
            self.store.process(job,dict(openai='sk',ai33='k'),threading.Event())
        self.assertEqual(job['state'],'done',job['message']);self.assertEqual(job['overlays'],[])
        self.assertTrue(any(w.startswith('Overlay') for w in job['warnings']))
        self.assertFalse(dubbing.options({})['overlay'])

    def test_burned_subtitles_are_gone_and_old_settings_fall_back_to_srt(self):
        self.assertNotIn('burn',dubbing.SUBTITLES);self.assertEqual(dubbing.options(dict(subtitles='burn'))['subtitles'],'file')

    def test_sequence_joins_short_overlays_and_cuts_to_video(self):
        a=self.overlay('a.mp4',['-f','lavfi','-i','testsrc2=s=160x120:r=30:d=1','-pix_fmt','yuv420p'])
        b=self.overlay('b.mp4',['-f','lavfi','-i','testsrc2=s=160x120:r=30:d=1','-pix_fmt','yuv420p'])
        with mock.patch.object(dubbing,'paragraph_request',return_value='Xin chào.'):
            job=self.job(background='remove',review=False,subtitles='none',overlay=True,overlay_timing='sequence',end_with_voice=False)
            self.store.process(job,dict(openai='sk',ai33='k'),threading.Event())
        self.assertEqual(job['state'],'done',job['message'])
        seq=job['overlays'][0]['sequence'];self.assertGreaterEqual(len(seq),4);self.assertTrue(set(seq)<={a['id'],b['id']})
        self.assertTrue(all(x!=y for x,y in zip(seq,seq[1:])))
        graph=(self.data/'dub'/job['id']/'export.ffgraph').read_text()
        self.assertIn('concat=n=',graph);self.assertIn('trim=',graph)
        self.assertAlmostEqual(dubbing.probe(self.data/'dub'/job['id']/'dubbed.mp4')['duration'],4,delta=.2)


class DemucsTests(PipelineBase):
    def test_demucs_found_via_python_module_runs_through_the_runner(self):
        fake=Path(self.tmp.name)/'pkgs'/'demucs';fake.mkdir(parents=True)
        (fake/'__init__.py').write_text('')
        (fake/'audio.py').write_text('def prevent_clip(wav,mode=None):return wav\n')
        # stand-in for demucs.separate: "separates" by copying the input to <out>/htdemucs/<name>/no_vocals.wav
        (fake/'separate.py').write_text("import shutil,sys\nfrom pathlib import Path\nsave_audio=None\ndef main(argv):\n"
            "    out=Path(argv[argv.index('-o')+1]);src=Path(argv[-1]);d=out/'htdemucs'/src.stem;d.mkdir(parents=True)\n"
            "    shutil.copyfile(src,d/'no_vocals.wav');(d/'vocals.wav').write_bytes(b'')\n")
        env=dict(os.environ,PYTHONPATH=str(fake.parent))
        with mock.patch.dict(os.environ,env),mock.patch.object(dubbing,'DEMUCS_ENV',Path(self.tmp.name)/'none'),mock.patch.object(dubbing.shutil,'which',return_value=None):
            cmd=dubbing.demucs_command(True)
            self.assertEqual(cmd[-1],str(dubbing.DEMUCS_RUNNER));self.assertTrue(dubbing.demucs_status()['available'])
            with mock.patch.object(dubbing,'paragraph_request',return_value='Xin chào.'):
                job=self.job(background='demucs',review=False,subtitles='none')
                self.store.process(job,dict(openai='sk',ai33='k'),threading.Event())
        self.assertEqual(job['state'],'done',job['message'])
        self.assertTrue((self.data/'dub'/job['id']/'background.wav').is_file())
        with mock.patch.object(dubbing,'DEMUCS_ENV',Path(self.tmp.name)/'none'),mock.patch.object(dubbing.shutil,'which',return_value=None),\
             mock.patch.object(dubbing.subprocess,'run',return_value=mock.Mock(returncode=1)):
            self.assertIsNone(dubbing.demucs_command(True))
        dubbing._demucs.clear()


class DesignTests(PipelineBase):
    """Dựng video mode and the design layer (nền + vùng hòa nền + khung + tiêu đề + nội dung) in the shared export."""
    DESIGN=dict(background='solid',color='#ff00ff',fade_start=50,fade_height=10,opacity=100,frame_style='none',title='CỐ ĐỊNH',body='',
                title_y=10,title_size=40,title_color='#00ff00',body_y=80)

    def pixel(self,path,x,y,t=1.0):
        return list(subprocess.run(['ffmpeg','-v','error','-ss',str(t),'-i',str(path),'-frames:v','1','-vf',f'crop=4:4:{x}:{y},scale=1:1','-f','rawvideo','-pix_fmt','rgb24','-'],capture_output=True).stdout)

    def test_design_mode_with_same_name_mp3_and_ai_texts_in_one_call(self):
        mp3=Path(self.tmp.name)/'clip.mp3';tone(mp3,3,500)
        calls=[]
        def texts(key,model,lines,settings):
            calls.append(lines);return dict(title='Nồi chiên gọn cho bếp nhỏ thật tiện',body='Chiên giòn ít dầu vệ sinh dễ dàng')
        with mock.patch.object(self.store,'enqueue'):
            key=self.store.create(dict(video_ids=[self.vid],mp3={self.vid:str(mp3)},options=dict(mode='design',background='remove',subtitles='none',design=self.DESIGN,title_source='ai',body_source='ai',title_words=6,end_with_voice=False)))[0]
        job=self.store.load(key);self.assertEqual(job['mp3'],'voice-src.mp3')
        with mock.patch.object(dubbing,'texts_request',side_effect=texts):
            self.store.process(job,dict(openai='sk',ai33=''),threading.Event())
        self.assertEqual(job['state'],'done',job['message']);self.assertEqual(len(calls),1)   # Whisper + ONE OpenAI call
        self.assertEqual(job['texts']['title'],'Nồi chiên gọn cho bếp nhỏ');self.assertTrue(any('Tiêu đề dài hơn 6 từ' in w for w in job['warnings']))
        out=self.data/'dub'/job['id']/'dubbed.mp4';info=dubbing.probe(out)
        self.assertEqual((info['video']['width'],info['video']['height']),(1080,1920));self.assertAlmostEqual(info['duration'],4,delta=.2)
        graph=(self.data/'dub'/job['id']/'export.ffgraph').read_text()
        self.assertIn('[designbg]',graph);self.assertIn('[designfr]',graph);self.assertIn('drawtext',graph)
        r,g,b=self.pixel(out,540,1700);self.assertTrue(r>200 and b>200 and g<80,(r,g,b))      # nền below the fade
        top=self.pixel(out,540,300);self.assertFalse(top[0]>200 and top[2]>200 and top[1]<80,top)   # video above the fade

    def test_fixed_and_file_texts_and_dub_with_design_in_the_same_call(self):
        seen={}
        def para(key,model,segments,seconds,limit,settings):
            seen['want']=dubbing.ai_texts_wanted(settings);return dict(text='Xin chào.',title='Tiêu đề AI',body='nội dung ngắn gọn')
        with mock.patch.object(dubbing,'paragraph_request',side_effect=para):
            job=self.job(background='remove',review=False,subtitles='none',design=self.DESIGN,title_source='fixed',body_source='ai')
            self.store.process(job,dict(openai='sk',ai33='k'),threading.Event())
        self.assertEqual(job['state'],'done',job['message']);self.assertTrue(seen['want'])
        self.assertEqual(self.store.texts_for(job),dict(title='CỐ ĐỊNH',body='nội dung ngắn gọn'))
        job['options']=dubbing.options({**job['options'],'title_source':'file','body_source':'none'})
        self.assertEqual(self.store.texts_for(job),dict(title='clip',body=''))
        self.assertEqual(job['options']['frame_canvas'],'9:16')
        with self.assertRaises(dubbing.DubError):dubbing.options(dict(design=dict(background='bad')))
        with self.assertRaises(dubbing.DubError):dubbing.options(dict(body_min=30,body_max=10))

    def test_same_name_mp3_keeps_its_own_sample_rate(self):
        mp3=Path(self.tmp.name)/'clip.mp3'
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=500:duration=4.0:sample_rate=44100','-c:a','libmp3lame',str(mp3)],check=True)
        with mock.patch.object(self.store,'enqueue'):
            key=self.store.create(dict(video_ids=[self.vid],mp3={self.vid:str(mp3)},options=dict(mode='design',background='remove',subtitles='none',design=self.DESIGN,title_source='fixed',body_source='none')))[0]
        job=self.store.load(key);self.store.process(job,dict(),threading.Event())
        self.assertEqual(job['state'],'done',job['message'])
        with wave.open(str(self.data/'dub'/key/'voice.wav')) as w:self.assertEqual(w.getframerate(),44100)
        self.assertEqual(job['voice_rate'],44100)
        # 4 s voice on a 4 s video (spoken up to 0.3 s before the end): voice a bit faster AND video a bit slower, both inside the limits
        g=job['groups'][0];self.assertGreater(g['tempo'],1);self.assertLess(g['tempo'],1.1);self.assertGreater(job['video_stretch'],1)
        self.assertAlmostEqual(g['tempo'],job['video_stretch'],delta=.03)

    def test_review_texts_waits_before_the_export_and_the_review_table_exports(self):
        mp3=Path(self.tmp.name)/'clip.mp3';tone(mp3,3,500)
        with mock.patch.object(self.store,'enqueue'):
            key=self.store.create(dict(video_ids=[self.vid],mp3={self.vid:str(mp3)},options=dict(mode='design',background='remove',subtitles='none',design=self.DESIGN,title_source='ai',body_source='ai',review_texts=True,end_with_voice=False)))[0]
        job=self.store.load(key)
        with mock.patch.object(dubbing,'texts_request',return_value=dict(title='Tiêu đề AI',body='nội dung AI')):
            self.store.process(job,dict(openai='sk',ai33=''),threading.Event())
        self.assertEqual((job['state'],job['step']),('review','export'),job['message'])
        self.assertFalse((self.data/'dub'/key/'dubbed.mp4').exists());self.assertEqual(job['steps']['tts'],'done')
        self.store.save(job)
        sent=[]
        with mock.patch.object(self.store,'enqueue',side_effect=lambda k,raw:sent.append(k)):
            r=self.store.review(dict(items=[dict(id=key,title='Tiêu đề đã sửa',body='nội dung AI'),dict(id='0'*32)]))
        self.assertEqual(r['done'],1);self.assertEqual(len(r['errors']),1);self.assertEqual(sent,[key])
        job=self.store.load(key);self.assertTrue(job['texts_passed'])
        self.assertEqual(self.store.texts_for(job)['title'],'Tiêu đề đã sửa')
        with mock.patch.object(dubbing,'texts_request',side_effect=AssertionError('no AI call after the review')):
            self.store.process(job,dict(),threading.Event())
        self.assertEqual(job['state'],'done',job['message']);self.assertTrue((self.data/'dub'/key/'dubbed.mp4').is_file())
        # "AI viết lại" from the table: one new call, then it waits for the review again
        job['state']='review';self.store.save(job)
        with mock.patch.object(self.store,'enqueue'):self.store.proceed(key,dict(**{'from':'texts'}))
        self.assertFalse(self.store.load(key)['texts_passed'])

    def test_estimate_and_parallel_setting(self):
        video=Path(self.tmp.name)/'clip.mp4';shutil.copyfile(self.data/self.vid/'source',video)
        d=self.store.estimate(dict(ids=[self.vid,'bad'],paths=[str(video),'/no/such.mp4','relative.mp4']))['durations']
        self.assertAlmostEqual(d[self.vid],4,delta=.2);self.assertIsNone(d['bad']);self.assertAlmostEqual(d[str(video)],4,delta=.2);self.assertIsNone(d['/no/such.mp4'])
        self.assertEqual(self.store.set_parallel(3)['parallel'],3)
        for bad in (0,5,'2',True):
            with self.assertRaises(dubbing.DubError):self.store.set_parallel(bad)
        again=dubbing.Store(self.data,self.settings,self.data,self.audio,media_engine.encoder_args)
        self.assertEqual(again.parallel,3)

    def test_parallel_workers_run_that_many_jobs_at_once(self):
        self.store.set_parallel(2);gate=threading.Event();seen=[];peak=[0]
        def slow(key):
            seen.append(key);peak[0]=max(peak[0],self.store.running);gate.wait(5)
        with mock.patch.object(self.store,'run_job',side_effect=slow):
            with self.store.lock:self.store.queue.extend(['a'*32,'b'*32,'c'*32])
            self.store.wake.set()
            for _ in range(50):
                if len(seen)>=2:break
                threading.Event().wait(.05)
            threading.Event().wait(.3)
            self.assertEqual(len(seen),2);self.assertEqual(peak[0],2);self.assertEqual(self.store.queue,['c'*32])
            gate.set()
            for _ in range(80):
                if len(seen)==3 and not self.store.running:break
                threading.Event().wait(.05)
        self.assertEqual(len(seen),3);self.assertEqual(self.store.running,0)


class OneFileTimestampTests(unittest.TestCase):
    def test_one_voice_file_is_cut_at_the_pauses_nearest_each_sentence(self):
        # three sentences of similar length; the short 0.1 s breath at 1.95 s is not taken as a sentence break
        self.assertEqual(dubbing.split_voice([(1.0,1.4),(1.9,2.0),(3.0,3.5)],[3,3,3],4.5),[(0.0,1.0),(1.4,3.0),(3.5,4.5)])
        self.assertEqual(dubbing.split_voice([],[1,1],2),[(0.0,1.0),(1.0,2)])   # no pauses: by length
        self.assertEqual(dubbing.split_voice([(1,1.2)],[1],3),[(0.0,3)])


class Ai33DubbingTests(PipelineBase):
    def test_ai33_timestamp_dubbing_uses_the_replacement_voice_and_srt(self):
        sent={}
        def create(key,audio,source,target,voice):
            sent.update(source=source,target=target,voice=voice,size=len(audio));return dict(task_id='dub1',state='submitted')
        srt='1\n00:00:00,300 --> 00:00:01,500\nXin chào cả nhà\n\n2\n00:00:02,000 --> 00:00:03,200\nCảm ơn đã xem\n'
        def download(url,target):
            Path(target).write_bytes(srt.encode() if url.endswith('.srt') else self.voice.read_bytes())
        done=dict(status='done',progress=100,audio_url='https://cdn.example/default.m4a',srt_url='https://cdn.example/vi.srt',replacement_audio_url='https://cdn.example/voice.mp3',replacement_status='done')
        with mock.patch.object(dubbing.ai33_audio,'create_dubbing',side_effect=create),mock.patch.object(dubbing.ai33_audio,'get_task',return_value=done),\
             mock.patch.object(dubbing.audio_files,'download',side_effect=download),mock.patch.object(dubbing,'transcribe_request') as asr:
            job=self.job(background='duck',review=False,subtitles='file',mode='ai33',language='en')
            self.store.process(job,dict(openai='',ai33='k'),threading.Event())
        self.assertEqual(job['state'],'done',job['message']);asr.assert_not_called()
        self.assertEqual((sent['source'],sent['target'],sent['voice']),('en','vi','edge_vi-VN-HoaiMyNeural'));self.assertGreater(sent['size'],1000)
        self.assertEqual((job['steps']['asr'],job['steps']['translate']),('skipped','skipped'))
        self.assertEqual([s['vi'] for s in job['segments']],['Xin chào cả nhà','Cảm ơn đã xem'])
        self.assertIn('Cảm ơn đã xem',(self.data/'dub'/job['id']/'vi.srt').read_text())
        self.assertAlmostEqual(dubbing.probe(self.data/'dub'/job['id']/'dubbed.mp4')['duration'],4,delta=.2)
        self.assertTrue((self.data/'dub'/job['id']/'background.wav').is_file())

    def test_ai33_mode_needs_no_openai_key_and_rejects_kokoro(self):
        # the real enqueue check runs (no OpenAI key needed), the worker is kept asleep
        with mock.patch.object(self.store.wake,'set'),mock.patch.object(dubbing,'openai_key',return_value=''):
            key=self.store.create(dict(video_ids=[self.vid],options=dict(voice_id='edge_vi-VN-HoaiMyNeural',mode='ai33'),ai33_key='k'))[0]
            with self.store.lock:self.store.queue.clear()
        self.assertEqual(self.store.load(key)['state'],'queued')
        with self.assertRaises(ValueError):dubbing.ai33_audio.create_dubbing('k',b'x',voice_id='kokoro_af_bella')


class StyleTests(unittest.TestCase):
    def test_style_presets_reach_both_prompts_and_strict_rule_is_always_on(self):
        import ai_translate
        seen=[]
        def call(path,key,body,ctype,timeout=0):
            seen.append(json.loads(body)['input'][0]['content'])
            text='{"text":"Xin chào"}' if 'dub_paragraph' in body.decode() else '{"lines":[{"id":0,"vi":"Xin chào"}]}'
            return dict(status='completed',output=[dict(type='message',content=[dict(type='output_text',text=text)])])
        opts=dubbing.options(dict(style='household',no_price=False))
        with mock.patch.object(dubbing,'openai_call',side_effect=call):
            dubbing.translate_request('k','m',[dict(id=0,zh='你好')],opts)
            dubbing.paragraph_request('k','m',[dict(start=0,end=1,zh='你好')],1,4,opts)
        for rules in seen:
            self.assertIn(ai_translate.STYLES['household'],rules);self.assertIn(ai_translate.STRICT,rules)
        self.assertEqual(set(ai_translate.STYLES),set(ai_translate.STYLE_LABELS));self.assertEqual(set(ai_translate.STYLES),set(ai_translate.HOOKS))
        with self.assertRaises(dubbing.DubError):dubbing.options(dict(style='x'))
