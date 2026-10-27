import io
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
import ai33_audio as api
import audio_files


class AudioApiTests(unittest.TestCase):
    def fields(self,**changes):
        raw=dict(text='Xin chào, đây là bản đọc tiếng Việt.',voice_id='edge_vi-VN-HoaiMyNeural',speed=1,api_key='dummy-ai33-key')
        raw.update(changes)
        return raw

    def test_create_uses_multipart_documented_endpoint_and_header(self):
        with patch.object(api.request,'urlopen',return_value=io.BytesIO(json.dumps(dict(success=True,task_id='task-123')).encode())) as call:
            result=api.create_tts(self.fields(pronunciation_dictionary_id=12,file_name='review-vietnamese'))
        req=call.call_args.args[0]
        self.assertEqual(req.full_url,'https://api.ai33.pro/v3/text-to-speech')
        self.assertEqual(req.get_method(),'POST')
        self.assertEqual(req.get_header('Xi-api-key'),'dummy-ai33-key')
        self.assertTrue(req.get_header('Content-type').startswith('multipart/form-data; boundary='))
        self.assertIn('Xin chào'.encode(),req.data)
        self.assertIn(b'name="voice_id"',req.data)
        self.assertIn(b'name="with_transcript"\r\n\r\nfalse',req.data)
        self.assertIn(b'name="pronunciation_dictionary_id"\r\n\r\n12',req.data)
        self.assertNotIn(b'receive_url',req.data)
        self.assertNotIn(b'dummy-ai33-key',req.data)
        self.assertNotIn('dummy-ai33-key',req.full_url)
        self.assertEqual(result['task_id'],'task-123')

    def test_voice_library_pagination_and_direct_prefixed_ids(self):
        result=dict(success=True,data=[dict(voice_id='edge_vi-VN-HoaiMyNeural',name='Hoài My',language='vi-VN',gender='Female',preview_url='https://media.example/preview.mp3')],pagination=dict(has_more=True))
        with patch.object(api.request,'urlopen',return_value=io.BytesIO(json.dumps(result).encode())) as call:
            rows=api.voice_library(dict(api_key='dummy-ai33-key',provider='edge',language='Vietnamese',gender='Female',page=2))
        self.assertIn('/v3/voices?provider=edge&page=2&page_size=30&language=Vietnamese&gender=Female',call.call_args.args[0].full_url)
        self.assertEqual(rows['voices'][0]['voice_id'],'edge_vi-VN-HoaiMyNeural')
        self.assertTrue(rows['has_more'])

    def test_task_states_and_metadata_from_common_documentation(self):
        for state in ('doing','done','error'):
            response=dict(id='task-123',status=state,progress=60,credit_cost=1,metadata=dict(audio_url='https://media.example/audio.mp3'),error_message='dummy-ai33-key')
            with patch.object(api.request,'urlopen',return_value=io.BytesIO(json.dumps(response).encode())) as call:
                task=api.get_task(dict(task_id='task-123',api_key='dummy-ai33-key'))
            self.assertEqual(call.call_args.args[0].full_url,'https://api.ai33.pro/v1/task/task-123')
            self.assertEqual(task['status'],state)
            self.assertEqual(task['audio_url'],'https://media.example/audio.mp3')
            self.assertNotIn('dummy-ai33-key',json.dumps(task))

    def test_credits_and_history_read_only_contract(self):
        for method,response,suffix in [(api.credits,dict(success=True,credits=123),'/v1/credits'),(api.list_tasks,dict(success=True,data=[dict(id='task-123',status='done',type='tts',metadata=dict(audio_url='https://media.example/audio.mp3'))],total=1),'/v1/tasks?page=1&limit=20')]:
            with patch.object(api.request,'urlopen',return_value=io.BytesIO(json.dumps(response).encode())) as call:
                result=method(dict(api_key='dummy-ai33-key'))
            self.assertTrue(call.call_args.args[0].full_url.endswith(suffix))
            self.assertEqual(call.call_args.args[0].get_method(),'GET')

    def test_no_key_and_no_automatic_retries(self):
        with patch.dict(api.os.environ,{},clear=True),patch.object(api.request,'urlopen') as call:
            with self.assertRaises(api.AudioError):api.create_tts(self.fields(api_key=''))
            call.assert_not_called()
        for exc in (HTTPError(api.ROOT,402,'dummy-ai33-key',{},io.BytesIO(b'dummy-ai33-key')),URLError('dummy-ai33-key')):
            with patch.object(api.request,'urlopen',side_effect=exc) as call,self.assertRaises(api.AudioError) as result:
                api.create_tts(self.fields())
            self.assertEqual(call.call_count,1)
            self.assertNotIn('dummy-ai33-key',str(result.exception))

    def test_invalid_voice_speed_and_fields_rejected_before_network(self):
        bad=[dict(voice_id='without-prefix'),dict(voice_id='edge_bad\nvoice'),dict(text=''),dict(speed=.4),dict(speed=1.6),dict(speed=True),dict(speed=math.nan),dict(with_transcript='false'),dict(pronunciation_dictionary_id=True),dict(file_name='x\ny')]
        with patch.object(api.request,'urlopen') as call:
            for fields in bad:
                with self.assertRaises(ValueError):api.create_tts(self.fields(**fields))
            call.assert_not_called()

    def test_missing_has_more_uses_total_and_requested_page_size(self):
        result=dict(data=[dict(voice_id='edge_one')],pagination=dict(total=210))
        with patch.object(api,'json_request',return_value=result):
            first=api.voice_library(dict(api_key='dummy-key',provider='edge',page=1,page_size=100))
            last=api.voice_library(dict(api_key='dummy-key',provider='edge',page=3,page_size=100))
        self.assertTrue(first['has_more']);self.assertFalse(last['has_more'])

    def test_capped_page_size_and_empty_page_stop(self):
        result=dict(data=[dict(voice_id='edge_one')],pagination=dict(total=210,page_size=30))
        with patch.object(api,'json_request',return_value=result):
            page=api.voice_library(dict(api_key='dummy-key',provider='edge',page=3,page_size=100))
        self.assertTrue(page['has_more']);self.assertEqual(page['page_size'],30)
        with patch.object(api,'json_request',return_value=dict(data=[],pagination=dict(has_more=True))):
            self.assertFalse(api.voice_library(dict(api_key='dummy-key'))['has_more'])

    def test_download_http_error_is_diagnostic_and_does_not_leak_signed_url(self):
        opener=unittest.mock.Mock()
        opener.open.side_effect=HTTPError('https://cdn.example/audio?token=secret',403,'secret',{},io.BytesIO(b'error'))
        with tempfile.TemporaryDirectory() as folder,patch.object(audio_files,'public_url',side_effect=lambda url:url),patch.object(audio_files.request,'build_opener',return_value=opener),self.assertRaises(api.AudioError) as result:
            audio_files.download('https://cdn.example/audio?token=secret',Path(folder)/'out')
        self.assertIn('AUDIO_HTTP_403',str(result.exception));self.assertNotIn('token=secret',str(result.exception))

    def test_task_paths_and_nonpublic_media_urls_rejected(self):
        for task in ('../private','x?key=secret',''):
            with self.assertRaises(ValueError):api.task_id(dict(task_id=task))
        for url in ('http://media.example/a.mp3','https://localhost/a','https://127.0.0.1/a','https://169.254.169.254/a','https://key@media.example/a','https://internal.local/a'):
            with self.assertRaises(api.AudioError):api.https_url(url)
        with patch.object(audio_files.socket,'getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]),self.assertRaises(api.AudioError):
            audio_files.public_url('https://media.example/a.mp3')

    def test_download_never_sends_api_key_to_media_host(self):
        class Media(io.BytesIO):
            headers={'Content-Length':'7'}
        opener=unittest.mock.Mock()
        opener.open.return_value=Media(b'ID3test')
        with tempfile.TemporaryDirectory() as folder,patch.object(audio_files,'public_url',side_effect=lambda url:url),patch.object(audio_files.request,'build_opener',return_value=opener):
            target=Path(folder)/'audio.bin'
            audio_files.download('https://media.example/audio.mp3',target)
            self.assertEqual(target.read_bytes(),b'ID3test')
        req=opener.open.call_args.args[0]
        self.assertIsNone(req.get_header('Xi-api-key'))
        self.assertIsNone(req.get_header('Authorization'))
        self.assertNotIn('Cookie',req.headers)

    def test_playlist_not_accepted_as_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'audio'
            path.write_bytes(b'#EXTM3U\nfile:///private/file')
            with self.assertRaises(api.AudioError):audio_files.media_format(path)


if __name__=='__main__':unittest.main()
