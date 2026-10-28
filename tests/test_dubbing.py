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


class PipelineTests(unittest.TestCase):
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

    def test_review_pause_then_full_dub_with_burned_subtitles(self):
        job=self.job(subtitles='burn',background='duck')
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
        job=self.job(subtitles='soft',background='remove',review=False)
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
