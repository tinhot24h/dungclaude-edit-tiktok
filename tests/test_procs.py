import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import procs

ROOT = Path(__file__).resolve().parents[1]


class ProcsTests(unittest.TestCase):
    def test_quit_stops_every_child_but_folder_windows(self):
        """⏻ / restart: FFmpeg, Demucs… still running are killed (Windows would leave them running)."""
        code = ('import subprocess,sys,time;sys.path.insert(0,%r);import procs;procs.track();'
                'a=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"]);'
                'b=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"]);'
                'n=procs.stop_all();print(n,a.poll() is not None,b.poll() is not None)') % str(ROOT)
        out = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=60).stdout.split()
        self.assertEqual(out, ['2', 'True', 'True'])

    def test_finished_and_folder_windows_are_left_alone(self):
        procs.track()
        done = subprocess.Popen([sys.executable, '-c', 'pass']);done.wait()
        with mock.patch.object(procs, 'KEEP', procs.KEEP + (Path(sys.executable).name.lower(),)):
            keep = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(30)'])
            try:
                self.assertNotIn(keep, procs.running());self.assertNotIn(done, procs.running())
            finally:
                keep.kill();keep.wait()

    def test_bind_is_a_no_op_off_windows(self):
        if sys.platform != 'win32':
            self.assertFalse(procs.bind(mock.MagicMock()))


class StoppingTests(unittest.TestCase):
    """A job whose FFmpeg was killed because the app quit keeps "running" (it resumes next start); a bug ends as a
    visible error instead of a job stuck in "running" and a dead queue."""
    def store(self, tmp):
        import dubbing
        data = Path(tmp)
        return dubbing, dubbing.Store(data, data / 'settings.json', data, data / 'audio', lambda *a: [])

    def test_unexpected_error_and_quit(self):
        with tempfile.TemporaryDirectory() as tmp:
            dubbing, store = self.store(tmp)
            job = dict(id='a' * 32, name='x', state='queued', step='asr', steps={s: 'pending' for s in dubbing.STEPS}, options={}, created='1')
            store.path(job['id']).mkdir(parents=True, exist_ok=True)
            store.save(job)
            with mock.patch.object(store, 'process', side_effect=ZeroDivisionError('boom')):
                store.run_job(job['id'])
            saved = store.load(job['id'])
            self.assertEqual(saved['state'], 'error');self.assertIn('ZeroDivisionError', saved['message'])
            store.save(dict(saved, state='queued'))
            store.stopping = True
            with mock.patch.object(store, 'process', side_effect=dubbing.DubError('FFmpeg bị dừng')):
                store.run_job(job['id'])
            self.assertEqual(store.load(job['id'])['state'], 'running')


class SafetyNetTests(unittest.TestCase):
    def test_a_bug_in_a_request_answers_500_json(self):
        import app
        handler = app.Handler.__new__(app.Handler)
        sent = {}
        handler.command, handler.path = 'GET', '/x'
        handler.respond = lambda code, content, mime=None: sent.update(code=code, content=content)

        def broken():
            raise KeyError('oops')
        app.Handler.safely(handler, broken)
        self.assertEqual(sent['code'], 500);self.assertIn('KeyError', sent['content']['error'])
        sent.clear()

        def full():
            raise OSError(28, 'No space left on device')
        app.Handler.safely(handler, full)
        self.assertIn('Ổ đĩa đã đầy', sent['content']['error'])


if __name__ == '__main__':
    unittest.main()
