import tempfile
import unittest
from pathlib import Path

import ai_translate
import dubbing
import library_store

PROFILE = dict(label='Bếp miền Tây', summary='Gần gũi kiểu miền Tây, kể chuyện bếp núc.', tone='vui, mộc mạc', open='hỏi một câu quen thuộc',
               flow='vấn đề → món đồ → lợi ích', use='"dữ thần", "ngon lành"', avoid='nói quá', example='Bà con coi nè!', titles='câu hỏi')


class StyleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory();d = Path(self.tmp.name)
        self.store = dubbing.Store(d, d / 's.json', d, d / 'a', lambda *a: [])

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_text_is_unchanged(self):
        """The prompt of an unedited văn phong is exactly what it was before the editor existed."""
        p = ai_translate.STYLE_PROFILES['review']
        old = (ai_translate.STYLES['review'] + ' Mức hào hứng: ' + ai_translate.ENERGY['mid'] + '.'
               + f'\n  · Giọng: {p["tone"]}.\n  · 3 giây đầu: {p["open"]} (câu đầu phải giữ chân người xem).\n  · Trình tự ý: {p["flow"]}.'
               + f'\n  · Nên dùng: {p["use"]}. Tránh: {p["avoid"]}.\n  · Câu mở mẫu (chỉ để cảm giọng, không chép): {p["example"]}')
        self.assertEqual(ai_translate.style_rules('review'), old)

    def test_edit_reset_and_custom(self):
        rows = self.store.styles()['styles'];self.assertEqual(len(rows), len(ai_translate.STYLE_LABELS))
        edited = dict(rows[0]['profile'], tone='GIỌNG MỚI')
        got = self.store.save_style(dict(id='review', profile=edited))
        self.assertTrue(next(r for r in got['styles'] if r['id'] == 'review')['edited'])
        self.store.save_style(dict(id='review', profile=ai_translate.default_profile('review')))   # saved back to the default text
        self.assertFalse(next(r for r in self.store.styles()['styles'] if r['id'] == 'review')['edited'])
        new = self.store.save_style(dict(profile=PROFILE))
        self.assertRegex(new['id'], '^c_[a-f0-9]{8}$');self.assertEqual(new['styles'][-1]['profile']['label'], 'Bếp miền Tây')
        self.store.delete_style(dict(id=new['id']));self.assertFalse(any(r['id'] == new['id'] for r in self.store.styles()['styles']))
        with self.assertRaises(dubbing.DubError):
            self.store.save_style(dict(profile=dict(PROFILE, label='')))
        with self.assertRaises(dubbing.DubError):
            self.store.save_style(dict(profile=dict(PROFILE, tone='x' * 401)))

    def test_jobs_carry_their_style(self):
        o = dubbing.options(dict(style='c_1234abcd', style_profile=PROFILE))
        self.assertEqual(o['style'], 'c_1234abcd')
        rules = dubbing.base_rules(o, 'ROLE')
        self.assertIn('Gần gũi kiểu miền Tây', rules);self.assertIn('Bà con coi nè!', rules)
        self.assertEqual(dubbing.options(dict(style='c_1234abcd'))['style'], 'review')   # no text with it: the default
        with self.assertRaises(dubbing.DubError):
            dubbing.options(dict(style='../x'))
        # a changed văn phong means a new translation (reuse keys differ), the look alone does not
        a = dubbing.reuse_keys(dubbing.options(dict(style='review')), 'src', '')
        b = dubbing.reuse_keys(dubbing.options(dict(style='review', style_profile=dict(ai_translate.default_profile('review'), tone='khác'))), 'src', '')
        self.assertNotEqual(a['trans'], b['trans']);self.assertEqual(a['asr'], b['asr'])
        self.assertIn('style_profile', dubbing.Store.KEEP_ON_REEXPORT)

    def test_prompt_preview(self):
        o = dict(style='c_1234abcd', style_profile=PROFILE, design=dict(title='x'), title_source='ai')
        got = self.store.prompt_preview(dict(options=o, video_name='am-sieu-toc'))
        self.assertEqual(len(got['calls']), 1);self.assertIn('Gần gũi kiểu miền Tây', got['calls'][0]['text'])
        self.assertEqual(self.store.prompt_preview(dict(options=dict(o, run_mode='build')))['calls'], [])
        lines = self.store.prompt_preview(dict(options=dict(mode='lines')))
        self.assertIn('Dịch theo timestamp', lines['calls'][0]['title'])


class LibraryMetaTests(unittest.TestCase):
    def test_list_shows_the_parts_without_a_second_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            library_store.save(tmp, 'dubpresets', dict(name='Khung hồng', data=dict(v=2, settings={}, parts=['design'], meta=dict(parts=['design'], desc='khung'))))
            library_store.save(tmp, 'dubpresets', dict(name='Mẫu cũ', data=dict(settings={})))
            rows = {r['name']: r for r in library_store.items(tmp, 'dubpresets')}
            self.assertEqual(rows['Khung hồng']['meta']['parts'], ['design']);self.assertNotIn('meta', rows['Mẫu cũ'])


if __name__ == '__main__':
    unittest.main()
