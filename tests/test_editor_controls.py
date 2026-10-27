import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import app
from design import settings,layout
import media_preview


class VerticalAlignmentTests(unittest.TestCase):
    def test_fixed_box_offsets_and_auto_height(self):
        base=dict(units='px',title='Một dòng',body='',title_y=100,title_height=200)
        top=layout(settings(base))[0]
        for align,factor in [('top',0),('middle',.5),('bottom',1)]:
            item=layout(settings({**base,'title_valign':align}))[0]
            self.assertAlmostEqual(item['content_y'],100+(200-top['natural_height'])*factor)
            self.assertEqual(item['y'],100)
        auto=layout(settings({**base,'title_height':0,'title_valign':'bottom'}))[0]
        self.assertEqual(auto['content_y'],100)
        with self.assertRaises(ValueError):settings({**base,'title_valign':'wrong'})


class ExportCancellationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.patch=patch.object(app,'DATA',self.root);self.patch.start()
        self.key='a'*32;self.folder=self.root/self.key;self.folder.mkdir()
        self.event=threading.Event();app.JOBS[self.key]={'state':'queued'};app.CANCELS[self.key]=self.event
    def tearDown(self):
        self.patch.stop();self.tmp.cleanup();app.JOBS.pop(self.key,None);app.CANCELS.pop(self.key,None)
    def test_cancel_queued_does_not_wait_for_other_export(self):
        with app.RENDER_LOCK:
            worker=threading.Thread(target=app.render,args=(self.key,[],{},'test',self.event));worker.start()
            self.event.set();worker.join(2)
            self.assertFalse(worker.is_alive())
        self.assertEqual(app.JOBS[self.key]['state'],'cancelled')
    def test_cancel_stops_worker_and_removes_partial_output(self):
        script="from pathlib import Path;import time;Path('review.mp4').write_bytes(b'partial');time.sleep(30)"
        worker=threading.Thread(target=app.render,args=(self.key,[sys.executable,'-c',script],dict(duration=30),'test',self.event));worker.start()
        deadline=time.monotonic()+5
        while not (self.folder/'review.mp4').exists() and time.monotonic()<deadline:time.sleep(.02)
        self.assertTrue((self.folder/'review.mp4').exists());self.event.set();worker.join(5)
        self.assertFalse(worker.is_alive());self.assertFalse((self.folder/'review.mp4').exists())
        self.assertEqual(app.JOBS[self.key]['state'],'cancelled');self.assertTrue(app.RENDER_LOCK.acquire(timeout=1));app.RENDER_LOCK.release()


class MediaPreviewTests(unittest.TestCase):
    def test_waveform_and_video_thumbnails_are_real_and_cached(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source.mp4';cache=root/'preview.json'
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=red:s=96x160:r=10:d=0.5','-f','lavfi','-i','sine=frequency=200:duration=0.5','-c:v','libx264','-threads','1','-c:a','aac','-shortest',str(source)],check=True)
            result=media_preview.analyze(source,cache,'video')
            self.assertEqual(len(result['thumbnails']),10)
            self.assertTrue(result['thumbnails'][0].startswith('data:image/jpeg;base64,/9j/'))
            self.assertGreater(max(result['peaks']),.01)
            with patch.object(media_preview.subprocess,'run',side_effect=AssertionError('cache should avoid FFmpeg')):
                self.assertEqual(media_preview.analyze(source,cache,'video'),result)


if __name__=='__main__':unittest.main()
