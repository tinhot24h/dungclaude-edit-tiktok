import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import free_music

ID='3f1a4c2e-5b6d-4e7f-8a9b-0c1d2e3f4a5b'


def track(**extra):
    return {**dict(id=ID,title='Sunny Day',creator='Ana',license='by',license_version='4.0',license_url='https://creativecommons.org/licenses/by/4.0/',
                url='https://cdn.example.org/sunny.mp3',duration=95000,foreign_landing_url='https://www.jamendo.com/track/1',source='jamendo'),**extra}


class FreeMusicTests(unittest.TestCase):
    def test_search_keeps_only_reusable_licences_and_builds_credit(self):
        rows=[track(),track(id='11111111-2222-4333-8444-555555555555',license='by-nc'),track(id='bad'),track(id='22222222-2222-4333-8444-555555555555',url='http://x/a.mp3')]
        with mock.patch.object(free_music,'get',return_value=dict(results=rows,result_count=4,page_count=3)) as get:
            result=free_music.search(dict(q='  vui   tươi ',category='music'))
        params=get.call_args[0][1]
        self.assertEqual((params['q'],params['license_type'],params['category']),('vui tươi','commercial,modification','music'))
        self.assertEqual(len(result['results']),1)
        row=result['results'][0]
        self.assertEqual((row['duration'],row['attribution_required'],result['pages']),(95,True,3))
        self.assertEqual(row['credit'],'"Sunny Day" của Ana (CC BY 4.0) · jamendo')
        for bad in (dict(q='x'*101),dict(page=0),dict(page=True),dict(category='video')):
            with self.assertRaises(free_music.MusicError):free_music.search(bad)

    def test_import_refetches_metadata_and_records_credit(self):
        with tempfile.TemporaryDirectory() as folder:
            sample=Path(folder)/'sample.wav'
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=330:duration=1',str(sample)],check=True)
            with mock.patch.object(free_music,'get',return_value=track()) as get,mock.patch.object(free_music,'fetch_file',side_effect=lambda url,target:shutil.copy(sample,target)) as fetch:
                asset=free_music.fetch(dict(id=ID),folder)
            self.assertEqual(get.call_args[0][0],'audio/'+ID+'/')
            self.assertEqual(fetch.call_args[0][0],'https://cdn.example.org/sunny.mp3')
            self.assertEqual((asset['source'],asset['name'],asset['attribution_required']),('openverse','Sunny Day',True))
            self.assertIn('CC BY',asset['credit']);self.assertTrue((Path(folder)/(asset['asset_id']+'.mp3')).is_file())
            with mock.patch.object(free_music,'get',return_value=track(license='by-nd')):
                with self.assertRaises(free_music.MusicError):free_music.fetch(dict(id=ID),folder)
            with self.assertRaises(free_music.MusicError):free_music.fetch(dict(id='../x'),folder)


if __name__=='__main__':
    unittest.main()
