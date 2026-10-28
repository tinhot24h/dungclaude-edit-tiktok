import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock
from urllib import error
import ai_translate
import dubbing
import output_folder
import test_dubbing


def reply(obj):
    return dict(status='completed', output=[dict(type='message', content=[dict(type='output_text', text=json.dumps(obj, ensure_ascii=False))])])


class PromptPieceTests(unittest.TestCase):
    def test_template_keeps_only_content_rules(self):
        kept, trimmed = dubbing.template_rules(ai_translate.DEFAULT_RULES)
        self.assertTrue(trimmed);self.assertIn('QUY TẮC NỘI DUNG', kept)
        for gone in ('HOOK', 'KỊCH BẢN', 'CHỮ HIỂN THỊ', 'Bạn là'):
            self.assertNotIn(gone, kept)
        self.assertLess(len(kept), len(ai_translate.DEFAULT_RULES) / 2)
        own = 'Viết vui vẻ.\n- Không nói tục.'
        self.assertEqual(dubbing.template_rules(own), (own, False))   # no headings: kept whole (with the "BỎ QUA" note)
        self.assertIn('BỎ QUA', dubbing.base_rules(dubbing.options(dict(instructions=own)), 'Vai'))
        self.assertNotIn('BỎ QUA', dubbing.base_rules(dubbing.options({}), 'Vai'))

    def test_title_style_variants_and_limits_in_prompt(self):
        o = dubbing.options(dict(title_style='question', title_chars=30, body_min_chars=50, body_max_chars=100))
        rules = dubbing.text_rules(o)
        self.assertIn('ĐÚNG 3 phương án TIÊU ĐỀ', rules);self.assertIn('ĐÚNG 2 phương án NỘI DUNG', rules)
        self.assertIn('18, 24 và 28 ký tự', rules);self.assertIn(dubbing.TITLE_STYLES['question'], rules)
        with self.assertRaises(dubbing.DubError):dubbing.options(dict(title_style='x'))

    def test_pick_longest_fitting_clean_variant(self):
        self.assertEqual(dubbing.pick_text(['Ngắn gọn', 'Nồi chiên gọn cho bếp nhỏ', 'Nồi chiên gọn nhẹ cho căn bếp nhỏ xinh của bạn'], 26)[:2], ('Nồi chiên gọn cho bếp nhỏ', False))
        self.assertEqual(dubbing.pick_text(['Giá chỉ 99k thôi', 'Nồi chiên tiện'], 26)[0], 'Nồi chiên tiện')        # price variant skipped
        self.assertEqual(dubbing.pick_text(['Nồi chiên tiện cho'], 26)[2], ['cụt'])
        text, cut, _ = dubbing.pick_text(['Nồi chiên không dầu gọn gàng cho căn bếp nhỏ', 'Nồi chiên không dầu siêu gọn cho mọi căn bếp nhỏ'], 26)
        self.assertTrue(cut);self.assertLessEqual(len(text), 26)
        body, cut, problems = dubbing.pick_text(['Chiên giòn ít dầu.', 'Chiên giòn ít dầu, vệ sinh dễ dàng và gọn gàng cho căn bếp nhỏ.'], 100, 50, body=True)
        self.assertEqual(body, 'Chiên giòn ít dầu, vệ sinh dễ dàng và gọn gàng cho căn bếp nhỏ.');self.assertEqual(problems, [])

    def test_finish_texts_keeps_options_and_flags(self):
        job = dict(options=dubbing.options(dict(title_chars=26)), warnings=[])
        dubbing.finish_texts(job, dict(title_options=['Bếp gọn', 'Nồi chiên gọn cho bếp nhỏ', 'Nồi chiên gọn nhẹ cho căn bếp nhỏ'],
                                       body_options=['Chiên giòn ít dầu, vệ sinh dễ dàng, hợp mọi căn bếp nhỏ.', 'Ngắn quá.']))
        self.assertEqual(job['texts']['title'], 'Nồi chiên gọn cho bếp nhỏ');self.assertEqual(len(job['text_options']['title']), 3)
        self.assertEqual(job['texts']['body'], 'Chiên giòn ít dầu, vệ sinh dễ dàng, hợp mọi căn bếp nhỏ.');self.assertEqual(job['text_flags'], dict(title=[], body=[]))
        self.assertEqual(job['warnings'], [])

    def test_two_file_names_and_alt_before_numbering(self):
        job = {}
        dubbing.set_file_name(job, dict(file_name='Váy maxi hoa nhí', file_name_alt='vay-maxi-di-bien'))
        self.assertEqual((job['file_name'], job['file_name_alt']), ('vay-maxi-hoa-nhi', 'vay-maxi-di-bien'))
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            self.assertEqual(output_folder.unique(d, 'vay-maxi-hoa-nhi', ['vay-maxi-di-bien']).name, 'vay-maxi-hoa-nhi.mp4')
            (d / 'vay-maxi-hoa-nhi.mp4').write_bytes(b'')
            self.assertEqual(output_folder.unique(d, 'vay-maxi-hoa-nhi', ['vay-maxi-di-bien']).name, 'vay-maxi-di-bien.mp4')
            (d / 'vay-maxi-di-bien.mp4').write_bytes(b'')
            self.assertEqual(output_folder.unique(d, 'vay-maxi-hoa-nhi', ['vay-maxi-di-bien']).name, 'vay-maxi-hoa-nhi-2.mp4')

    def test_one_call_carries_hint_frames_texts_and_names(self):
        seen = []
        def call(path, key, body, ctype, timeout=0):
            seen.append(json.loads(body));return reply(dict(text='Xin chào', title_options=['A'], body_options=['B'], file_name='noi-chien-mini', file_name_alt='noi-chien-gon'))
        o = dubbing.options(dict(design={}, title_source='ai'))
        o['design'] = {'x': 1}
        ctx = dict(hint='nồi chiên', video_name='douyin123', images=['data:image/jpeg;base64,AAAA'])
        with mock.patch.object(dubbing, 'openai_call', side_effect=call):
            got = dubbing.paragraph_request('k', 'gpt-4.1-mini', [dict(start=0, end=1, zh='你好')], 1, 4, o, ctx)
        self.assertEqual(len(seen), 1);self.assertEqual(got['file_name_alt'], 'noi-chien-gon')
        dev, user = seen[0]['input']
        self.assertIn('title_options', seen[0]['text']['format']['schema']['required']);self.assertIn('file_name_alt', seen[0]['text']['format']['schema']['required'])
        self.assertIn('hint (nếu có)', dev['content']);self.assertIn('1 khung hình', dev['content'])
        self.assertEqual(user['content'][1], dict(type='input_image', image_url='data:image/jpeg;base64,AAAA', detail='low'))
        self.assertEqual(json.loads(user['content'][0]['text'])['hint'], 'nồi chiên')

    def test_model_without_images_is_asked_again_without_them(self):
        seen = []
        def call(path, key, body, ctype, timeout=0):
            seen.append(json.loads(body))
            if len(seen) == 1:
                e = dubbing.DubError('bad', 502);e.http = 400;raise e
            return reply(dict(title_options=['A'], body_options=['B'], file_name='a-b-c', file_name_alt='a-b-d'))
        ctx = dict(images=['data:image/jpeg;base64,AAAA'])
        with mock.patch.object(dubbing, 'openai_call', side_effect=call):
            dubbing.texts_request('k', 'custom-model', ['你好'], dubbing.options({}), ctx)
        self.assertEqual(len(seen), 2);self.assertIsInstance(seen[1]['input'][1]['content'], str);self.assertNotIn('- Ảnh:', seen[1]['input'][0]['content'])
        self.assertTrue(ctx['dropped_images'])


class TranslatePageTests(unittest.TestCase):
    def test_page_uses_the_same_limits_variants_and_file_names(self):
        answer = dict(hook='A', hook_options=['A'], script='Xin chào', title='Kệ gia vị gọn gàng cho căn bếp nhỏ xinh của bạn',
                      title_options=['Kệ gọn', 'Kệ gia vị gọn cho bếp nhỏ', 'Kệ gia vị gọn gàng cho căn bếp nhỏ xinh của bạn'],
                      body='Ngắn.', body_options=['Ngắn.', 'Lắp nhanh, chịu lực tốt, giúp góc bếp luôn gọn gàng và sạch sẽ mỗi ngày.'],
                      file_name='Kệ gia vị gọn', file_name_alt='ke-gia-vi-chiu-luc')
        got = ai_translate.import_manual(dict(text=json.dumps(answer, ensure_ascii=False), title_chars=26))
        self.assertEqual(got['title'], 'Kệ gia vị gọn cho bếp nhỏ');self.assertEqual(len(got['title_options']), 3)
        self.assertEqual(got['body'], 'Lắp nhanh, chịu lực tốt, giúp góc bếp luôn gọn gàng và sạch sẽ mỗi ngày.')
        self.assertEqual((got['file_name'], got['file_name_alt']), ('ke-gia-vi-gon', 'ke-gia-vi-chiu-luc'));self.assertEqual(got['warnings'], [])
        prompt = ai_translate.manual_prompt(dict(source='x', title_style='pain'))
        self.assertIn('title_options', prompt);self.assertIn('file_name_alt', prompt);self.assertIn('nỗi đau – giải pháp: nêu một phiền toái', prompt)


class RetryTests(unittest.TestCase):
    def test_openai_retries_passing_failures_but_not_an_empty_quota(self):
        class Body:
            def __enter__(self):return self
            def __exit__(self, *a):pass
            def read(self, n):return b'{"ok":1}'
        calls = []
        def flaky(req, timeout=0):
            calls.append(1)
            if len(calls) < 3:raise error.URLError('reset')
            return Body()
        with mock.patch.object(dubbing, 'RETRY_WAITS', (0, 0)), mock.patch.object(dubbing.request, 'urlopen', side_effect=flaky):
            self.assertEqual(dubbing.openai_call('responses', 'k', b'{}', 'application/json'), {'ok': 1})
        self.assertEqual(len(calls), 3)
        quota = error.HTTPError('u', 429, 'x', {}, None)
        quota.read = lambda n=0: b'{"error":{"code":"insufficient_quota"}}'
        calls.clear()
        def empty(req, timeout=0):
            calls.append(1);raise quota
        with mock.patch.object(dubbing, 'RETRY_WAITS', (0, 0)), mock.patch.object(dubbing.request, 'urlopen', side_effect=empty):
            with self.assertRaises(dubbing.DubError) as got:dubbing.openai_call('responses', 'k', b'{}', 'application/json')
        self.assertEqual(len(calls), 1);self.assertIn('quota', str(got.exception))

    def test_ai33_retries_reads_but_never_a_create_that_may_have_been_received(self):
        a = dubbing.ai33_audio
        calls = []
        def timeout(req, timeout=0):
            calls.append(req.get_method());raise TimeoutError()
        with mock.patch.object(a, 'RETRY_WAITS', (0, 0)), mock.patch.object(a.request, 'urlopen', side_effect=timeout):
            with self.assertRaises(a.AudioError):a.json_request('/v1/task/x', 'k')
            self.assertEqual(calls, ['GET'] * 3);calls.clear()
            with self.assertRaises(a.AudioError):a.json_request('/v3/text-to-speech', 'k', b'x', 'text/plain')
            self.assertEqual(calls, ['POST'])          # a timeout may mean "received": not sent again
        refused = error.URLError(ConnectionRefusedError())
        calls.clear()
        def down(req, timeout=0):
            calls.append(1);raise refused
        with mock.patch.object(a, 'RETRY_WAITS', (0, 0)), mock.patch.object(a.request, 'urlopen', side_effect=down):
            with self.assertRaises(a.AudioError):a.json_request('/v3/text-to-speech', 'k', b'x', 'text/plain')
        self.assertEqual(len(calls), 3)                # the connection never opened: safe to try again


class ReuseTests(test_dubbing.PipelineBase):
    def run_one(self, **opts):
        with mock.patch.object(self.store, 'enqueue'):
            key = self.store.create(dict(video_ids=[self.vid], options={**dict(voice_id='edge_vi-VN-HoaiMyNeural', mode='paragraph', background='remove', subtitles='none'), **opts}))[0]
        job = self.store.load(key)
        self.store.process(job, dict(openai='sk', ai33='k'), threading.Event())
        self.assertEqual(job['state'], 'done', job['message'])
        return job

    def test_same_video_new_look_reuses_translation_and_voice(self):
        para = mock.MagicMock(side_effect=lambda *a, **k: dict(text='Xin chào.', file_name='quan-ao-nu-hottrend'))
        with mock.patch.object(dubbing, 'paragraph_request', para), mock.patch.object(dubbing, 'video_frames', return_value=[]):
            first = self.run_one()
            asr_calls = dubbing.transcribe_request.call_count
            again = self.run_one(frame_zoom=120, adjust=True, adjust_brightness=20)
            self.assertEqual(para.call_count, 1);self.assertEqual(dubbing.transcribe_request.call_count, asr_calls);self.assertEqual(len(self.tasks), 1)
            self.assertEqual(again['reused']['level'], 'voice');self.assertEqual(again['file_name'], 'quan-ao-nu-hottrend')
            other = self.run_one(voice_id='edge_vi-VN-NamMinhNeural')   # other voice: translation kept, voice made again
            self.assertEqual(other['reused']['level'], 'trans');self.assertEqual(para.call_count, 1);self.assertEqual(len(self.tasks), 2)
            fresh = self.run_one(reuse=False)
            self.assertNotIn('reused', fresh);self.assertEqual(para.call_count, 2)
            est = self.store.estimate(dict(ids=[self.vid], options=dict(voice_id='edge_vi-VN-HoaiMyNeural', mode='paragraph', background='remove')))
            row = est['videos'][self.vid]
            self.assertEqual(row['reuse'], 'voice');self.assertEqual(row['cost']['usd'], 0);self.assertEqual(row['cost']['ai33_chars'], 0)
            design = dict(test_dubbing.DesignTests.DESIGN)
            est = self.store.estimate(dict(ids=[self.vid], options=dict(voice_id='edge_vi-VN-HoaiMyNeural', mode='paragraph', background='remove', design=design, title_source='ai')))
            row = est['videos'][self.vid]
            self.assertEqual(row['reuse'], 'voice');self.assertGreater(row['cost']['usd'], 0);self.assertEqual(row['cost']['uses'], ['viết tiêu đề/nội dung + tên file'])
            est = self.store.estimate(dict(ids=[self.vid], options=dict(voice_id='edge_vi-VN-HoaiMyNeural', mode='paragraph', language='en')))
            row = est['videos'][self.vid]
            self.assertIsNone(row['reuse']);self.assertGreater(row['cost']['usd'], 0);self.assertGreater(row['cost']['ai33_chars'], 0)

    def test_voice_sample_is_bought_once(self):
        a = self.store.voice_sample(dict(voice_id='edge_vi-VN-HoaiMyNeural', ai33_key='k'))
        b = self.store.voice_sample(dict(voice_id='edge_vi-VN-HoaiMyNeural', ai33_key='k'))
        self.assertEqual((a['cached'], b['cached'], a['id']), (False, True, b['id']));self.assertEqual(len(self.tasks), 1)
        self.assertTrue(self.store.sample_file(a['id']).is_file())
        self.assertNotEqual(self.store.voice_sample(dict(voice_id='edge_vi-VN-HoaiMyNeural', voice_speed=1.2, ai33_key='k'))['id'], a['id'])

    def test_silent_video_gets_ai_texts_from_its_frames(self):
        seen = []
        def texts(key, model, lines, settings, context=None):
            seen.append((lines, context));return dict(title_options=['Nồi chiên gọn'], body_options=['Chiên giòn ít dầu, vệ sinh dễ dàng, hợp mọi căn bếp nhỏ xinh.'], file_name='noi-chien-gon')
        design = dict(test_dubbing.DesignTests.DESIGN)
        with mock.patch.object(self.store, 'enqueue'):
            key = self.store.create(dict(video_ids=[self.vid], hints={self.vid: 'nồi chiên không dầu'}, options=dict(mode='design', design=design, background='remove', subtitles='none', reuse=False)))[0]
        job = self.store.load(key)
        with mock.patch.object(dubbing, 'texts_request', side_effect=texts), mock.patch.object(dubbing, 'probe', side_effect=lambda p, real=dubbing.probe: dict(real(p), audio=None)):
            self.store.process(job, dict(openai='sk'), threading.Event())
        self.assertEqual(job['state'], 'done', job['message']);self.assertEqual(job['steps']['asr'], 'skipped')
        self.assertEqual(seen[0][0], []);self.assertEqual(seen[0][1]['hint'], 'nồi chiên không dầu');self.assertEqual(len(seen[0][1]['images']), 3)
        self.assertTrue(seen[0][1]['images'][0].startswith('data:image/jpeg;base64,'));self.assertEqual(job['file_name'], 'noi-chien-gon')


if __name__ == '__main__':
    unittest.main()
