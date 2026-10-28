import json
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
    def test_review_pause_then_full_dub_with_burned_subtitles(self):
        job=self.job(subtitles='burn',background='duck',mode='lines',review=True)
        self.store.process(job,dict(openai='sk-test',ai33='k'),threading.Event())
        self.assertEqual(job['state'],'review');self.assertEqual([s['vi'] for s in job['segments']],['Xin chào','Cảm ơn mọi người'])
        self.assertTrue((self.data/'dub'/job['id']/'zh.srt').is_file())
        job['review_passed']=True;self.store.process(job,dict(openai='sk-test',ai33='k'),threading.Event())
        self.assertEqual(job['state'],'done',job['message'])
        self.assertTrue(all(v in ('done','skipped') for v in job['steps'].values()))
        self.assertEqual(sorted(self.tasks.values()),['Cảm ơn mọi người','Xin chào'])
        out=self.data/'dub'/job['id']/'dubbed.mp4';info=dubbing.probe(out)
        self.assertAlmostEqual(info['duration'],4,delta=.15);self.assertIsNotNone(info['audio'])
        self.assertGreater(job['groups'][0]['tempo'],1)
        saved=Path(job['outputs']['saved_path']);self.assertTrue(saved.is_file());self.assertTrue(saved.with_suffix('.srt').is_file())
        with wave.open(str(self.data/'dub'/job['id']/'voice.wav')) as w:self.assertAlmostEqual(w.getnframes()/w.getframerate(),4,delta=.01)
        # editing one line re-voices only that line
        self.store.edit_lines(job['id'],[dict(i=1,vi='Cảm ơn')])
        self.assertTrue(job['groups'][0].get('file'));self.assertFalse(job['groups'][1].get('file'))
        self.store.process(job,dict(openai='sk-test',ai33='k'),threading.Event())
        self.assertEqual(job['state'],'done');self.assertEqual(len(self.tasks),3)

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
        self.assertEqual(job['groups'][0]['tempo'],1.0)
        lines=job['vi_lines'];self.assertEqual([l['vi'] for l in lines],['Xin chào mọi người.','Cảm ơn đã xem nha.'])
        self.assertAlmostEqual(lines[1]['start'],.2+1.3,delta=.15)
        self.assertIn('Xin chào mọi người.',(self.data/'dub'/job['id']/'vi.srt').read_text())
        # editing the paragraph re-voices it (one new task)
        self.store.edit_paragraph(job['id'],'Xin chào.')
        self.assertEqual((job['groups'],job['steps']['tts']),([],'pending'))

    def test_sentence_lines_snap_to_pauses(self):
        lines=dubbing.sentence_lines('Một hai ba. Bốn năm sáu bảy tám.',10,6,pauses=[2.6])
        self.assertEqual([(l['start'],l['end']) for l in lines],[(10,12.6),(12.6,16)])
        self.assertEqual(dubbing.sentence_lines('',0,3),[])

    def test_slow_video_down_when_the_voice_is_longer(self):
        long=Path(self.tmp.name)/'long.mp3';tone(long,6,600)
        with mock.patch.object(dubbing,'paragraph_request',return_value='Một đoạn rất dài. Hai câu.'),\
             mock.patch.object(dubbing.ai33_audio,'get_task',return_value=dict(status='done',audio_url='https://cdn.example/a.mp3')),\
             mock.patch.object(dubbing.audio_files,'download',side_effect=lambda url,target:Path(target).write_bytes(long.read_bytes())):
            job=self.job(subtitles='burn',background='duck',review=False,align='video')
            self.store.process(job,dict(openai='sk',ai33='k'),threading.Event())
        self.assertEqual(job['state'],'done',job['message'])
        self.assertGreater(job['video_stretch'],1.5)
        self.assertAlmostEqual(dubbing.probe(self.data/'dub'/job['id']/'dubbed.mp4')['duration'],job['output_duration'],delta=.2)
        self.assertEqual(len(job['vi_lines']),2)
        self.assertAlmostEqual(job['output_duration'],.2*job['video_stretch']+6+.3,delta=.1)

    def test_mp3_follows_video_both_ways(self):
        with mock.patch.object(dubbing,'paragraph_request',return_value='Ngắn.'):
            job=self.job(background='remove',review=False,align='voice',subtitles='none')
            self.store.process(job,dict(openai='sk',ai33='k'),threading.Event())
        # 2.2s voice in a 3.75s window is slowed down to the natural floor of 0.8×
        self.assertEqual(job['state'],'done',job['message']);self.assertEqual(job['groups'][0]['tempo'],.8);self.assertEqual(job['video_stretch'],1)


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
