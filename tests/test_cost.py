import threading
import unittest.mock
import unittest

import dubbing
import test_dubbing


class Ai33PriceTests(unittest.TestCase):
    """ai33.pro: $5 per 1,000,000 characters (spaces and punctuation included)."""
    def test_estimate_and_price(self):
        o = dubbing.options(dict(mode='paragraph', rate=4.2))
        c = dubbing.cost(o, 60)
        self.assertEqual(c['ai33_chars'], round(60 * 4.2 * 4.3))
        self.assertAlmostEqual(c['ai33_usd'], c['ai33_chars'] * 5 / 1e6, places=6)
        self.assertFalse(c['ai33_exact'])
        exact = dubbing.cost(o, 60, 'trans', voice_chars=1234)
        self.assertEqual((exact['ai33_chars'], exact['ai33_exact']), (1234, True))
        self.assertAlmostEqual(exact['ai33_usd'], 0.00617, places=6)
        self.assertEqual(dubbing.cost(o, 60, 'voice')['ai33_usd'], 0)   # the old voice is reused: nothing to buy

    def test_voice_text_chars(self):
        self.assertEqual(dubbing.voice_text_chars(dict(paragraph=' Xin chào cả nhà. '), 'paragraph'), len('Xin chào cả nhà.'))
        job = dict(segments=[dict(vi='Xin chào'), dict(vi='Cảm ơn mọi người!'), dict(vi='')])
        self.assertEqual(dubbing.voice_text_chars(job, 'lines'), len('Xin chào.\nCảm ơn mọi người!'))
        self.assertIsNone(dubbing.voice_text_chars(dict(segments=[]), 'lines'));self.assertIsNone(dubbing.voice_text_chars(None, 'lines'))


class Ai33SpendTests(test_dubbing.PipelineBase):
    def test_characters_sent_are_counted(self):
        before = dubbing.AI33_SPEND.summary()['chars']
        job = self.job(mode='paragraph', background='remove', subtitles='none')
        with unittest.mock.patch.object(dubbing, 'paragraph_request', return_value='Chào cả nhà, hôm nay mình giới thiệu một món đồ rất hay.'):
            self.store.process(job, dict(openai='sk', ai33='k'), threading.Event())
        self.assertEqual(job['state'], 'done', job['message'])
        got = dubbing.AI33_SPEND.summary()
        self.assertEqual(got['chars'] - before, len(self.tasks['t0']))
        self.assertAlmostEqual(got['usd'], got['chars'] * 5 / 1e6, places=4);self.assertEqual(got['price'], 5.0)


if __name__ == '__main__':
    unittest.main()
