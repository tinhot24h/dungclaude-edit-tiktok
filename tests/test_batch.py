import json
import os
import shutil
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


class CoverTests(unittest.TestCase):
    """"Lấp đầy · cắt viền" + rotation 0.5° + zoom 103 % + an X/Y offset used to show black corners."""
    def border(self, lines, W, H):
        cmd = ['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'color=c=0xd0c0a0:s={W}x{H}:d=1', '-filter_complex', ';'.join(lines),
               '-map', '[out]', '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'gray', '-']
        px = subprocess.run(cmd, capture_output=True, check=True).stdout
        rows = [px[y * W:(y + 1) * W] for y in (0, H - 1)]
        cols = [bytes(px[y * W + x] for y in range(H)) for x in (0, W - 1)]
        return min(min(r) for r in rows + cols)

    def test_rotation_and_offset_never_show_black(self):
        self.assertEqual(dubbing.cover_scale(720, 1280, 720, 1280, 360, 640, 0), 1.0)
        for fx, fy, rot in ((0, 0, .5), (2, 0, .5), (4, -3, .5), (10, 5, 8)):
            o = dubbing.options(dict(frame_canvas='9:16', frame_fit='cover', frame_zoom=103, frame_rotate=rot, frame_x=fx, frame_y=fy, out_resolution='720'))
            lines, (W, H) = dubbing.frame_graph(o, dict(width=720, height=1280), [], [])
            lines[-1] = lines[-1].replace('[vout]', '[out]')
            self.assertGreater(self.border(lines, W, H), 150, (fx, fy, rot))
        for vx, vy, rot in ((0, 0, .5), (13, -8, .5), (0, 0, -4)):
            d = dict(units='px', video_x=vx, video_y=vy, video_width=720, video_height=1280, video_zoom=103, video_rotation=rot, video_fit='cover', background='color', color='#000000')
            self.assertGreater(self.border(dubbing.design_video(d, 720, 1280) + ['[framed]null[out]'], 720, 1280), 150, (vx, vy, rot))
        # "Giữ toàn bộ" on a 9:16 source cut by "Cắt viền mép" fills the frame instead of leaving 1–2 px black or blurred strips
        for fit in ('contain', 'blur'):
            o = dubbing.options(dict(frame_canvas='9:16', frame_fit=fit, edge_trim=4, frame_rotate=.5, out_resolution='720'))
            lines, (W, H) = dubbing.frame_graph(o, dict(width=720, height=1280), [], [])
            self.assertNotIn('decrease', ';'.join(lines));self.assertNotIn('boxblur', ';'.join(lines))
            lines[-1] = lines[-1].replace('[vout]', '[out]')
            self.assertGreater(self.border(lines, W, H), 150, fit)
            wide, _ = dubbing.frame_graph(o, dict(width=1280, height=720), [], [])   # a really different shape is still fitted
            self.assertIn('decrease', ';'.join(wide))
        d = dict(units='px', video_x=0, video_y=0, video_width=720, video_height=1280, video_zoom=100, video_rotation=0, video_fit='contain', background='color', color='#000000')
        self.assertGreater(self.border(dubbing.design_video(d, 720, 1280, trim=['crop=iw-8:ih-8:4:4'], source=(712, 1272)) + ['[framed]null[out]'], 720, 1280), 150)
        # a box smaller than the frame is left as placed
        small = dict(units='px', video_x=100, video_y=100, video_width=400, video_height=700, video_zoom=100, video_rotation=5, video_fit='cover', background='color', color='#000000')
        self.assertLess(self.border(dubbing.design_video(small, 720, 1280) + ['[framed]null[out]'], 720, 1280), 20)


class CaptionMusicTests(test_dubbing.PipelineBase):
    def run_job(self, **opts):
        para = mock.MagicMock(side_effect=lambda *a, **k: dict(text='Chào cả nhà. Hôm nay mình giới thiệu món đồ rất hay.', file_name='video-thu-nghiem'))
        with mock.patch.object(dubbing, 'paragraph_request', para), mock.patch.object(dubbing, 'video_frames', return_value=[]):
            job = self.job(mode='paragraph', background='remove', subtitles='none', out_resolution='source', **opts)
            self.store.process(job, dict(openai='sk', ai33='k'), threading.Event())
        self.assertEqual(job['state'], 'done', job['message'])
        return job, self.data / 'dub' / job['id']

    def test_words_share_the_time_and_light_up_one_by_one(self):
        words = dubbing.caption_words([dict(start=0, end=2, vi='một hai ba bốn năm sáu')], 3)
        self.assertEqual(len(words), 6);self.assertEqual(words[0][2], ['một', 'hai', 'ba']);self.assertEqual(words[3][2], ['bốn', 'năm', 'sáu'])
        self.assertEqual((words[0][0], words[-1][1]), (0, 2));self.assertEqual([w[3] for w in words], [0, 1, 2, 0, 1, 2])
        o = dubbing.options(dict(captions=True, caption_style='box', caption_upper=True))
        text, n = dubbing.captions_ass([dict(start=0, end=1, vi='xin {chào}')], o, 1080, 1920)
        self.assertEqual(n, 2);self.assertIn('XIN', text);self.assertNotIn('{CHÀO}', text);self.assertIn('Be Vietnam Pro Black', text)
        with self.assertRaises(dubbing.DubError):dubbing.options(dict(caption_hi='yellow'))
        row = [dict(start=0, end=1, vi='một hai ba')]
        ev = lambda st: [l for l in dubbing.captions_ass(row, dubbing.options(dict(captions=True, caption_style=st)), 1080, 1920)[0].splitlines() if l.startswith('Dialogue: 1')]
        self.assertEqual(ev('karaoke')[2].count('\\c&H004DE1FF}'), 3)          # every word read so far stays lit
        self.assertIn('\\alpha&HFF&', ev('reveal')[0]);self.assertNotIn('\\alpha&HFF&', ev('reveal')[2])
        self.assertTrue(all(l.count(' ') <= 1 + l.count('{') for l in ev('single')));self.assertNotIn('hai', ev('single')[0].split('}')[-2])
        for st in dubbing.CAPTION_STYLES:
            self.assertEqual(len(ev(st)), 3, st)

    def test_captions_are_burned_in_with_their_font(self):
        job, folder = self.run_job(captions=True, caption_y=50, caption_size=60)
        graph = (folder / 'export.ffgraph').read_text()
        self.assertIn('ass=captions.ass:fontsdir=capfonts', graph);self.assertEqual(len(list((folder / 'capfonts').iterdir())), 1)
        self.assertIn('Dialogue:', (folder / 'captions.ass').read_text(encoding='utf-8'))
        off, folder2 = self.run_job()
        self.assertNotIn('ass=', (folder2 / 'export.ffgraph').read_text())

    def test_reexport_renders_with_the_new_settings(self):
        job, folder = self.run_job(frame_canvas='9:16', frame_rotate=0)
        first = Path(job['outputs']['saved_path'])
        with mock.patch.object(self.store, 'enqueue'):
            self.store.batch(dict(action='reexport', ids=[job['id']], options=dict(job['options'], frame_rotate=2, captions=True, out_resolution='720')))
        job = self.store.load(job['id'])
        with mock.patch.object(dubbing, 'video_frames', return_value=[]), mock.patch.object(dubbing, 'paragraph_request', side_effect=AssertionError('no new AI call')):
            self.store.process(job, dict(openai='sk', ai33='k'), threading.Event())
        self.assertEqual(job['state'], 'done', job['message'])
        graph = (folder / 'export.ffgraph').read_text()
        self.assertIn('rotate=0.034906585', graph);self.assertIn('ass=captions.ass', graph)          # 2° and the captions: the new look
        self.assertEqual(dubbing.probe(folder / 'dubbed.mp4')['video']['width'], 720)
        self.assertNotEqual(Path(job['outputs']['saved_path']), first);self.assertTrue(first.is_file())   # a new file, the old one kept
        self.assertEqual(len(self.tasks), 1)                                                            # no new voice

    def test_music_from_the_library_by_style_ducked_under_the_voice(self):
        src = Path(self.tmp.name) / 'beat.mp3'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=220:duration=2', str(src)], check=True)
        tmp = Path(self.tmp.name) / 'beat.upload';shutil.copyfile(src, tmp)
        track = self.store.import_music(tmp, 'beat.mp3')
        other = Path(self.tmp.name) / 'b2.upload';shutil.copyfile(src, other);news = self.store.import_music(other, 'tin.mp3')
        self.store.set_music_styles(news['id'], ['news'])
        with self.assertRaises(dubbing.DubError):self.store.set_music_styles(track['id'], ['rock'])
        job, folder = self.run_job(music=True, style='news', music_volume=30)
        self.assertEqual(job['music']['id'], news['id'])                      # the track tagged with the văn phong
        graph = (folder / 'export.ffgraph').read_text()
        self.assertIn('sidechaincompress', graph);self.assertIn('amix=inputs=2', graph)
        self.assertAlmostEqual(dubbing.probe(folder / 'dubbed.mp4')['duration'], job.get('output_duration', job['duration']), delta=.2)   # the music never makes the video longer
        job2, folder2 = self.run_job(music=True, music_duck=False, music_ids=[track['id']])
        self.assertEqual(job2['music']['id'], track['id']);self.assertNotIn('sidechaincompress', (folder2 / 'export.ffgraph').read_text())
        self.store.delete_music(track['id']);self.store.delete_music(news['id'])
        job3, _ = self.run_job(music=True)
        self.assertTrue(any(w.startswith('Nhạc nền') for w in job3['warnings']))


class SpendTests(unittest.TestCase):
    def test_openai_calls_add_up_per_month(self):
        import tempfile, json as j
        with tempfile.TemporaryDirectory() as tmp:
            spend = dubbing.Spend();spend.path = Path(tmp) / 'openai_spend.json'
            spend.add('responses', j.dumps(dict(model='gpt-4.1-mini')).encode(), dict(usage=dict(input_tokens=1_000_000, output_tokens=500_000)))
            spend.add('audio/transcriptions', b'multipart', dict(duration=120))
            spend.add('responses', b'not json', dict())   # odd replies never break a job
            got = spend.summary()
            self.assertEqual(got['calls'], 3);self.assertAlmostEqual(got['usd'], .4 + .8 + .012, places=4)
            data = j.loads(spend.path.read_text())
            data.update({f'2000-{m:02d}': dict(usd=1, calls=1) for m in range(1, 13)});spend.path.write_text(j.dumps(data))
            spend.add('audio/transcriptions', b'', dict(duration=60))
            self.assertEqual(len(j.loads(spend.path.read_text())), 12)   # only a year of months is kept


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

    def test_edge_trim_removes_the_border_of_the_source(self):
        src = self.data / self.vid / 'source'
        framed = src.with_name('framed.mp4')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=0x2060a0:s=172x312:r=30:d=4', '-f', 'lavfi', '-i', 'sine=frequency=300:duration=4',
                        '-vf', 'pad=180:320:4:4:color=white', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', '-f', 'mp4', str(framed)], check=True)
        framed.replace(src)
        def column(job, x):
            out = self.data / 'dub' / job['id'] / 'dubbed.mp4'
            w = dubbing.probe(out)['video']['width']
            return list(subprocess.run(['ffmpeg', '-v', 'error', '-ss', '1', '-i', str(out), '-frames:v', '1', '-vf', f'crop=2:ih:{w - 2 if x < 0 else x}:0,scale=1:1',
                                        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout)
        white = self.run_job(out_resolution='source')
        self.assertGreater(min(column(white, -1)), 200)                    # the source's white border reaches the edge
        clean = self.run_job(out_resolution='source', edge_trim=4)
        right, left = column(clean, -1), column(clean, 0)
        self.assertLess(right[0], 120);self.assertLess(left[0], 120)       # gone on both sides: the blue picture fills the frame
        self.assertEqual(self.video(self.data / 'dub' / clean['id'] / 'dubbed.mp4')[:2], (180, 320))
        with self.assertRaises(dubbing.DubError):dubbing.options(dict(edge_trim=41))

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

    def test_batch_actions_touch_only_the_right_states(self):
        a, b, c = (self.job(mode='paragraph') for _ in range(3))
        for j, state in ((a, 'error'), (b, 'review'), (c, 'paused')):
            j['state'] = state;self.store.save(j)
        with mock.patch.object(self.store, 'enqueue') as enqueue:
            got = self.store.batch(dict(action='retry', ids=[a['id'], b['id'], c['id']]))
        self.assertEqual((got['done'], got['skipped']), (1, 2))          # a job waiting for review is never sent on unseen
        self.assertEqual([x.args[0] for x in enqueue.call_args_list], [a['id']])
        with mock.patch.object(self.store, 'enqueue'):
            self.assertEqual(self.store.batch(dict(action='resume', ids=[a['id'], b['id'], c['id']]))['done'], 1)
        self.store.queue[:] = [a['id'], b['id'], c['id']]
        self.assertEqual(self.store.batch(dict(action='top', ids=[c['id']]))['waiting'], [c['id'], a['id'], b['id']])
        self.assertEqual(self.store.batch(dict(action='bottom', ids=[c['id'], a['id']]))['waiting'], [b['id'], c['id'], a['id']])
        self.store.queue[:] = []
        got = self.store.batch(dict(action='delete', ids=[b['id']]))
        self.assertEqual(got['done'], 1);self.assertFalse((self.data / 'dub' / b['id']).exists())
        with self.assertRaises(dubbing.DubError):self.store.batch(dict(action='format', ids=[]))
        with self.assertRaises(dubbing.DubError):self.store.batch(dict(action='delete', ids=['../x']))

    def test_reexport_changes_only_the_look(self):
        a = self.job(mode='paragraph', style='review', frame_zoom=100)
        a['state'] = 'done';a['steps'] = {k: 'done' for k in a['steps']};self.store.save(a)
        with mock.patch.object(self.store, 'enqueue') as enqueue:
            got = self.store.batch(dict(action='reexport', ids=[a['id']], options=dict(frame_zoom=110, captions=True, style='news', voice_id='other', mode='lines', trim_start=3)))
        self.assertEqual(got['done'], 1);enqueue.assert_called_once()
        job = self.store.load(a['id'])
        self.assertEqual((job['options']['frame_zoom'], job['options']['captions']), (110, True))          # the look is new
        self.assertEqual((job['options']['style'], job['options']['mode'], job['options']['trim_start']), ('review', 'paragraph', 0))   # the content is not
        self.assertEqual(job['steps']['export'], 'pending');self.assertEqual(job['steps']['tts'], 'done')   # only the export runs again

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
