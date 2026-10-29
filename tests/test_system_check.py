import tempfile
import unittest
from pathlib import Path
from unittest import mock
import system_check

ROOT=Path(__file__).resolve().parents[1]


class SystemCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.data=Path(self.tmp.name)
        self.settings=self.data/'settings.json'

    def tearDown(self):self.tmp.cleanup()

    def check(self,**keys):
        with mock.patch('secrets_store.get',side_effect=lambda p:keys.get(p,'')),mock.patch('output_folder.load',return_value={'output_dir':str(self.data)}):
            return system_check.run(ROOT,self.data,self.settings,network=False)

    def test_rows_have_states_and_fixes(self):
        d=self.check()
        keys={r['key'] for r in d['rows']}
        self.assertTrue({'python','ffmpeg','openai','ai33','output','fonts'}<=keys)
        for r in d['rows']:
            self.assertIn(r['state'],('ok','warn','bad','info'))
            if r['state'] in ('warn','bad'):self.assertTrue(r['fix'],r)
        self.assertEqual(d['version'],(ROOT/'VERSION').read_text().strip())

    def test_missing_keys_warn_saved_keys_ok_without_network(self):
        rows={r['key']:r for r in self.check()['rows']}
        self.assertEqual(rows['openai']['state'],'warn')
        rows={r['key']:r for r in self.check(openai='sk-x',ai33='k')['rows']}
        self.assertEqual((rows['openai']['state'],rows['ai33']['state']),('ok','ok'))

    def test_worst_state_wins(self):
        with mock.patch('shutil.which',return_value=None):d=self.check(openai='a',ai33='b')
        self.assertEqual(d['state'],'bad')
        self.assertEqual({r['key']:r['state'] for r in d['rows']}['ffmpeg'],'bad')

    def test_bad_output_folder(self):
        with mock.patch('secrets_store.get',return_value='k'),mock.patch('output_folder.load',return_value={'output_dir':str(self.data/'nope'/'x')}),\
             mock.patch('output_folder.check_dir',side_effect=ValueError('Thư mục không tồn tại')):
            rows={r['key']:r for r in system_check.run(ROOT,self.data,self.settings,network=False)['rows']}
        self.assertEqual(rows['output']['state'],'bad')


if __name__=='__main__':unittest.main()
