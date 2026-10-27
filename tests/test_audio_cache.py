import array
import math
import shutil
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
import audio_files


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg and FFprobe required for actual MP3 conversion')
class AudioCacheTests(unittest.TestCase):
    def test_actual_mp3_conversion_cache_and_no_second_provider_request(self):
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder)
            wavefile=directory/'input.wav'
            with wave.open(str(wavefile),'wb') as out:
                out.setnchannels(1)
                out.setsampwidth(2)
                out.setframerate(44100)
                samples=array.array('h',(int(7000*math.sin(2*math.pi*440*i/44100)) for i in range(11025)))
                out.writeframes(samples.tobytes())
            def fake_download(url,target):
                shutil.copyfile(wavefile,target)
            detail=dict(status='done',audio_url='https://media.example/audio.wav')
            with patch.object(audio_files.api,'get_task',return_value=detail) as get_task,patch.object(audio_files,'download',side_effect=fake_download) as download:
                result=audio_files.cache(dict(task_id='cache-test-123',api_key='dummy-ai33-key'),directory/'cache')
                again=audio_files.cache(dict(task_id='cache-test-123'),directory/'cache')
            self.assertEqual(result['url'],again['url'])
            self.assertEqual(get_task.call_count,1)
            self.assertEqual(download.call_count,1)
            self.assertGreater(result['duration'],.2)
            self.assertGreater(result['bytes'],100)
            mp3=directory/'cache'/(result['asset_id']+'.mp3')
            subprocess.run(['ffmpeg','-v','error','-i',str(mp3),'-f','null','-'],check=True,capture_output=True)
            self.assertEqual(sorted(p.suffix for p in (directory/'cache').iterdir()),['.json','.mp3'])
            self.assertNotIn('dummy-ai33-key',next((directory/'cache').glob('*.json')).read_text())


if __name__=='__main__':unittest.main()
