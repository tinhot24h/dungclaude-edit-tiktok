import json
import threading
import unittest
from unittest import mock

import dubbing
import test_dubbing

DESIGN = dict(title='', body='Câu nội dung mẫu', title_size=40, body_size=30)


class RunModeOptionsTests(unittest.TestCase):
    def test_modes(self):
        self.assertEqual((dubbing.options({})['run_mode'], dubbing.options({})['mode']), ('full', 'paragraph'))
        for r in ('texts', 'build'):
            o = dubbing.options(dict(run_mode=r, mode='lines'))
            self.assertEqual((o['run_mode'], o['mode']), (r, 'design'))
        self.assertEqual(dubbing.options(dict(mode='design'))['run_mode'], 'texts')   # an old "Dựng video" setting
        with self.assertRaises(dubbing.DubError):
            dubbing.options(dict(run_mode='x'))

    def test_build_never_asks_the_ai(self):
        o = dubbing.options(dict(run_mode='build', design=DESIGN, title_source='ai', body_source='ai', review_texts=True))
        self.assertFalse(dubbing.ai_texts_wanted(o));self.assertFalse(o['review_texts'])
        c = dubbing.cost(o, 60)
        self.assertEqual((c['usd'], c['ai33_chars'], c['ai33_minutes'], c['uses']), (0, 0, 0, []))
        t = dubbing.options(dict(run_mode='texts', design=DESIGN, title_source='ai'))
        self.assertTrue(dubbing.ai_texts_wanted(t));self.assertEqual(dubbing.cost(t, 60)['ai33_chars'], 0)

    def test_quick_test_is_always_build(self):
        o = dubbing.options(dict(run_mode='full', test_seconds=5, review=True))
        self.assertEqual((o['run_mode'], o['mode'], o['test_seconds'], o['review']), ('build', 'design', 5.0, False))
        for bad in (-1, 31, True, 'x'):
            with self.assertRaises(dubbing.DubError):
                dubbing.options(dict(test_seconds=bad))
        self.assertIn('run_mode', dubbing.Store.KEEP_ON_REEXPORT);self.assertIn('test_seconds', dubbing.Store.KEEP_ON_REEXPORT)


class RunModePipelineTests(test_dubbing.PipelineBase):
    def run_job(self, keys=None, **opts):
        job = self.job(**opts)
        self.store.process(job, keys or {}, threading.Event())
        return job

    def test_build_exports_without_any_key_or_call(self):
        with mock.patch.object(dubbing, 'texts_request') as texts, mock.patch.object(dubbing, 'paragraph_request') as para:
            job = self.run_job(run_mode='build', design=DESIGN, title_source='ai', body_source='ai', background='keep', subtitles='none')
        self.assertEqual(job['state'], 'done', job['message'])
        dubbing.transcribe_request.assert_not_called();texts.assert_not_called();para.assert_not_called()
        self.assertEqual(self.store.texts_for(job), dict(title='clip', body='Câu nội dung mẫu'))   # file name + fixed text
        self.assertTrue((self.out / 'clip-dung.mp4').is_file())

    def test_build_reuses_only_the_ai_texts_of_an_earlier_run(self):
        old = self.job(design=DESIGN, title_source='ai', body_source='ai', reuse=True)
        old.update(texts=dict(title='Tiêu đề AI', body='Nội dung AI'), file_name='ten-ai', warnings=['Đoạn văn dài 25/14 tiếng'], paragraph='x',
                   state='done', steps={s: 'done' for s in dubbing.STEPS})
        self.store.save(old);self.store.__dict__.pop('_sources', None)
        new = self.job(run_mode='build', design=DESIGN, title_source='ai', body_source='ai', reuse=True)
        self.assertEqual(new['texts'], old['texts']);self.assertEqual(new['file_name'], 'ten-ai')
        self.assertEqual(new['warnings'], []);self.assertNotIn('paragraph', new);self.assertEqual(new['reused']['level'], 'texts')

    def test_a_job_that_cannot_be_queued_is_not_left_waiting(self):
        before = set(p.name for p in self.store.root.iterdir())
        with mock.patch.object(dubbing.secrets_store, 'get', return_value=''), mock.patch.dict('os.environ', REVIEW_OPENAI_KEY='', OPENAI_API_KEY=''):
            with self.assertRaises(dubbing.DubError):
                self.store.create(dict(video_ids=[self.vid], options=dict(run_mode='texts', design=DESIGN, title_source='ai', reuse=False)))
        self.assertEqual(set(p.name for p in self.store.root.iterdir()), before)

    def test_quick_test_cuts_to_5_seconds_and_stays_in_the_app(self):
        job = self.run_job(test_seconds=2, design=DESIGN, title_source='fixed', body_source='fixed', background='keep', subtitles='none')
        self.assertEqual(job['state'], 'done', job['message'])
        out = self.data / 'dub' / job['id'] / 'dubbed.mp4'
        self.assertAlmostEqual(dubbing.probe(out)['duration'], 2, delta=.2)
        self.assertFalse(any(self.out.glob('*.mp4')) if self.out.exists() else False)
        self.assertNotIn('saved_path', job['outputs']);self.assertIn('xuất thử', job['message'])


if __name__ == '__main__':
    unittest.main()
