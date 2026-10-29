import json
import os
import subprocess
import threading
import unittest
from pathlib import Path
from unittest import mock
import dubbing
import output_folder
import test_dubbing


class OutputSizeTests(unittest.TestCase):
    def test_resolution_scales_the_frame_and_the_source_shape(self):
        o = lambda **k: dubbing.options(k)
        self.assertEqual(dubbing.frame_size(o(frame_canvas='9:16', out_resolution='720'), {}), (720, 1280))
        self.assertEqual(dubbing.frame_size(o(frame_canvas='9:16', out_resolution='4k'), {}), (2160, 3840))
        self.assertEqual(dubbing.frame_size(o(frame_canvas='1:1', out_resolution='2k'), {}), (1440, 1440))
        src = dict(width=720, height=1280)
        self.assertEqual(dubbing.frame_size(o(out_resolution='1080'), src), (1080, 1920))
        self.assertEqual(dubbing.frame_size(o(out_resolution='source'), src), (720, 1280))
        self.assertEqual(dubbing.frame_size(o(out_resolution='source', frame_canvas='9:16'), src), (1080, 1920))
        with self.assertRaises(dubbing.DubError):dubbing.options(dict(out_fps='24'))
        self.assertEqual(dubbing.source_fps(dict(avg_frame_rate='60000/1001')), 60000 / 1001)


class BatchExportTests(test_dubbing.PipelineBase):
    def run_job(self, **opts):
        para = mock.MagicMock(side_effect=lambda *a, **k: dict(text='Xin chào.', file_name='video-thu-nghiem'))
        with mock.patch.object(dubbing, 'paragraph_request', para), mock.patch.object(dubbing, 'video_frames', return_value=[]):
            job = self.job(mode='paragraph', background='remove', subtitles='none', **opts)
            self.store.process(job, dict(openai='sk', ai33='k'), threading.Event())
        self.assertEqual(job['state'], 'done', job['message'])
        return job

    def video(self, path):
        info = dubbing.probe(path)
        return info['video']['width'], info['video']['height'], round(dubbing.source_fps(info['video'])), info['duration']

    def test_size_fps_cap_and_one_encode_for_the_cut(self):
        src = self.data / self.vid / 'source'
        sixty = src.with_name('sixty.mp4')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=s=180x320:r=60:d=4', '-f', 'lavfi', '-i', 'sine=frequency=300:duration=4',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', '-f', 'mp4', str(sixty)], check=True)
        sixty.replace(src)
        encodes = []
        real = dubbing.run
        def spy(cmd, *a, **k):
            if '-c:v' in cmd:
                encodes.append(cmd)
            return real(cmd, *a, **k)
        with mock.patch.object(dubbing, 'run', side_effect=spy):
            job = self.run_job(out_resolution='720', out_fps='30', trim_start=1)
        folder = self.data / 'dub' / job['id']
        w, h, fps, duration = self.video(folder / 'dubbed.mp4')
        self.assertEqual((w, h, fps), (720, 1280, 30))           # 180×320 source → 720p, 60 fps → 30 fps
        self.assertLess(duration, 3.2)                            # 1 s cut off the 4 s source
        self.assertFalse((folder / 'trimmed.mp4').exists());self.assertEqual(len(encodes), 1)   # the cut is not encoded on its own
        job = self.run_job(out_resolution='source', out_fps='60')
        self.assertEqual(self.video(self.data / 'dub' / job['id'] / 'dubbed.mp4')[:3], (180, 320, 60))

    def test_export_is_stored_once_and_reexport_never_touches_the_saved_file(self):
        job = self.run_job(out_resolution='source')
        folder, saved = self.data / 'dub' / job['id'], Path(job['outputs']['saved_path'])
        self.assertTrue(os.path.samefile(folder / 'dubbed.mp4', saved))           # same drive: one file, two names
        before = saved.stat().st_mtime_ns, saved.stat().st_size
        job['steps']['export'] = 'pending'
        with mock.patch.object(dubbing, 'video_frames', return_value=[]):
            self.store.process(job, dict(openai='sk', ai33='k'), threading.Event())
        again = Path(job['outputs']['saved_path'])
        self.assertNotEqual(again, saved);self.assertEqual((saved.stat().st_mtime_ns, saved.stat().st_size), before)
        # another drive (link refused): only the copy in the output folder is kept, and it is what gets served
        job['steps']['export'] = 'pending'
        with mock.patch.object(output_folder.os, 'link', side_effect=OSError('cross-device')), mock.patch.object(dubbing, 'video_frames', return_value=[]):
            self.store.process(job, dict(openai='sk', ai33='k'), threading.Event())
        self.assertFalse((folder / 'dubbed.mp4').exists());self.assertTrue(Path(job['outputs']['saved_path']).is_file())

    def test_clean_up_keeps_queued_videos_and_queue_resumes_after_restart(self):
        job = self.job(mode='paragraph')
        self.assertIn(self.vid, self.store.videos_in_use())
        job['state'] = 'running';self.store.save(job)
        again = dubbing.Store(self.data, self.settings, self.data, self.audio, test_dubbing.media_engine.encoder_args)
        with mock.patch.object(again, 'enqueue') as enqueue:
            self.assertEqual(again.resume_interrupted(), 1)
        enqueue.assert_called_once_with(job['id'], {})
        again.set_parallel(None, resume=False)
        self.assertFalse(json.loads((self.data / 'dub' / 'queue.json').read_text())['resume'])
        third = dubbing.Store(self.data, self.settings, self.data, self.audio, test_dubbing.media_engine.encoder_args)
        job2 = third.load(job['id']);job2['state'] = 'running';third.save(job2)
        with mock.patch.object(third, 'enqueue') as enqueue:
            self.assertEqual(third.resume_interrupted(), 0)
        enqueue.assert_not_called()
        job2['state'] = 'done';third.save(job2)
        self.assertNotIn(self.vid, third.videos_in_use())


class Batch2Tests(test_dubbing.PipelineBase):
    def test_cpu_threads_and_demucs_slots(self):
        with mock.patch.object(dubbing.os, 'cpu_count', return_value=16):
            self.assertEqual((dubbing.cpu_threads(1), dubbing.cpu_threads(4), dubbing.cpu_threads(16)), (16, 4, 2))
            self.store.parallel, self.store.running = 2, 2
            args = self.store.video_codec('cpu', 'high')
        self.assertEqual(args[args.index('-threads') + 1], '8')
        slots = dubbing.Slots(1)
        self.assertTrue(slots.acquire(False));self.assertFalse(slots.acquire(False))
        slots.set(2);self.assertTrue(slots.acquire(False));slots.release();slots.release()
        self.store.set_parallel(None, demucs=3)
        self.assertEqual((dubbing.DEMUCS_SLOT.limit, self.store.queue_info()['demucs']), (3, 3))
        self.store.set_parallel(None, demucs=1)

    def test_queue_sends_only_changes(self):
        a = self.job(mode='paragraph');b = self.job(mode='paragraph')
        first = self.store.jobs_since(0)
        self.assertTrue(first['full']);self.assertEqual(len(first['jobs']), 2)
        for j in (a, b):
            j['state'] = 'done';self.store.save(j)
        stamp = self.store.jobs_since(0)['stamp']
        quiet = self.store.jobs_since(stamp + 1)
        self.assertEqual((quiet['jobs'], set(quiet['ids'])), ([], {a['id'], b['id']}))
        import time;time.sleep(.02)
        a['message'] = 'đổi';self.store.save(a)
        self.assertEqual([j['id'] for j in self.store.jobs_since(stamp + 1)['jobs']], [a['id']])

    def test_sweep_frees_temp_files_and_reexport_rebuilds_them(self):
        para = mock.MagicMock(side_effect=lambda *a, **k: dict(text='Xin chào.', file_name='video-don-tam'))
        with mock.patch.object(dubbing, 'paragraph_request', para), mock.patch.object(dubbing, 'video_frames', return_value=[]):
            job = self.job(mode='paragraph', background='duck', subtitles='file')
            self.store.process(job, dict(openai='sk', ai33='k'), threading.Event())
            folder = self.data / 'dub' / job['id']
            self.assertTrue((folder / 'background.wav').is_file())
            before = self.store.storage()
            self.assertGreater(before['temp'], 0)
            self.assertEqual(self.store.sweep(5)['cleaned'], 0)               # too recent for a 5-day sweep
            done = self.store.sweep(0)
            self.assertEqual(done['cleaned'], 1);self.assertGreater(done['freed'], 0);self.assertEqual(done['temp'], 0)
            left = sorted(p.name for p in folder.iterdir())
            self.assertEqual(left, sorted(['job.json', 'zh.srt', 'vi.srt', 'g0.wav', 'dubbed.mp4']))
            job['steps']['export'] = 'pending'
            self.store.process(job, dict(openai='sk', ai33='k'), threading.Event())
        self.assertEqual(job['state'], 'done', job['message']);self.assertEqual(para.call_count, 1);self.assertEqual(len(self.tasks), 1)   # no new AI / voice
        self.assertTrue((folder / 'background.wav').is_file());self.assertTrue((folder / 'dubbed.mp4').is_file())


if __name__ == '__main__':
    unittest.main()
