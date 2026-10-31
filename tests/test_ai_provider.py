import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
import ai_provider as ai
import dubbing
import secrets_store


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for target, value in [('ai_provider.ROOT', self.root), ('secrets_store.PATH', self.root/'secrets.json')]:
            p = patch(target, value); p.start(); self.addCleanup(p.stop)
        ai.write('gemini-models.json', dict(models=['verified-primary', 'verified-fallback'], checked_at=1))
        self.sdk = MagicMock()
        p=patch.object(ai, 'client'); self.factory=p.start();self.addCleanup(p.stop)
        self.factory.return_value.__enter__.return_value=self.sdk
        self.response=SimpleNamespace(text='{"text":"Xin chào"}', usage_metadata=SimpleNamespace(prompt_token_count=11,candidates_token_count=4,total_token_count=15))
        self.sdk.models.generate_content.return_value=self.response
        self.body=dict(model='verified-primary',input=[dict(role='developer',content='unchanged rules'),dict(role='user',content='source')],max_output_tokens=100,text=dict(format=dict(schema=dict(type='object',required=['text'],properties=dict(text=dict(type='string'))))))

    def test_legacy_and_provider_cache(self):
        old=dubbing.options({}); self.assertEqual(old['provider'],'openai')
        new=dubbing.options(dict(provider='gemini',model='verified-primary'))
        a=dubbing.reuse_keys(old,'source','');b=dubbing.reuse_keys(new,'source','')
        self.assertEqual(a['asr'],b['asr']);self.assertNotEqual(a['trans'],b['trans'])
        with self.assertRaises(dubbing.DubError):dubbing.options(dict(provider='unknown'))

    def test_key_security_and_no_overwrite(self):
        secrets_store.save('openai','test-openai-key')
        status=secrets_store.save('gemini','test-gemini-key')
        self.assertNotIn('test-gemini-key',json.dumps(status))
        secrets_store.forget_removed()
        self.assertEqual(secrets_store.get('openai'),'test-openai-key')
        self.assertEqual(secrets_store.get('gemini'),'test-gemini-key')
        secrets_store.delete('gemini'); self.assertTrue(secrets_store.get('openai'))

    def test_schema_usage_and_prompt(self):
        raw=ai.generate(self.body,{},10)
        self.assertEqual(raw['status'],'completed')
        config=self.sdk.models.generate_content.call_args.kwargs['config']
        self.assertEqual(config.system_instruction,'unchanged rules')
        row=next(iter(next(iter(ai.read('ai-usage.json',{}).values())).values()))
        self.assertEqual((row['tasks'],row['attempts'],row['total_tokens']),(1,1,15))

    def test_invalid_json_is_not_success(self):
        for value in ['{}','{"text":""}','[]','not json']:
            self.response.text=value
            with self.assertRaises(ai.ProviderError):ai.generate(self.body,{},10)

    def test_unverified_model_rejected(self):
        with self.assertRaises(ai.ProviderError):ai.generate(dict(self.body,model='invented'),{},10)
        self.sdk.models.generate_content.assert_not_called()

    def test_retry_and_same_provider_fallback(self):
        class RateLimit(Exception):
            code=429
            response=SimpleNamespace(headers={'retry-after':'0'})
        self.sdk.models.generate_content.side_effect=[RateLimit(),RateLimit(),RateLimit(),self.response]
        with patch.object(ai.time,'sleep') as sleep, patch.object(dubbing,'openai_call') as openai:
            raw=ai.generate(self.body,dict(fallback_enabled=True,fallback_model='verified-fallback'),10)
        self.assertEqual(raw['model'],'verified-fallback');openai.assert_not_called()
        self.assertEqual(sleep.call_count,2)

    def test_auth_error_never_retried_or_leaked(self):
        class Forbidden(Exception):code=403
        self.sdk.models.generate_content.side_effect=Forbidden('secret-test-key')
        with self.assertRaises(ai.ProviderError) as caught:
            ai.generate(self.body,dict(fallback_enabled=True,fallback_model='verified-fallback'),10)
        self.assertNotIn('secret-test-key',str(caught.exception))
        self.assertEqual(self.sdk.models.generate_content.call_count,1)

    def test_catalog_filters_actions(self):
        self.sdk.models.list.return_value=[SimpleNamespace(name='models/real-id',supported_actions=['generateContent']),SimpleNamespace(name='models/embed',supported_actions=['embedContent'])]
        self.assertEqual(ai.models(True)['models'],['real-id'])

    def test_legacy_adapter(self):
        with patch.object(dubbing,'responses_call',return_value={'status':'completed'}) as old:
            dubbing.provider_call(self.body,None,{},10)
        old.assert_called_once_with(self.body,None,10)

    def test_segment_id_validation(self):
        self.response.text='{"lines":[{"id":99,"vi":"xin chào"}]}'
        with self.assertRaises(dubbing.DubError):
            dubbing.translate_request('', 'verified-primary',[dict(id=1,zh='你好')],dubbing.options(dict(provider='gemini')))

from test_dubbing import PipelineBase
import threading

class GeminiPipelineTests(PipelineBase):
    def test_whisper_gemini_ai33_render_and_checkpoint(self):
        self.patches[1].stop()  # exercise the real translation adapter and existing postprocessing
        job=self.job(provider='gemini',model='verified-primary',mode='lines',vision=False,review=False)
        def answer(body, settings, timeout):
            source=json.loads(body['input'][1]['content'])
            fields=body['text']['format']['schema']['properties']
            result={'lines':[dict(id=row['id'],vi='Xin chào mọi người') for row in source['lines']]}
            for name in fields:
                if name!='lines':result[name]='Video hay' if fields[name]['type']=='string' else ['Video hay']
            return dict(status='completed',output=[dict(type='message',content=[dict(type='output_text',text=json.dumps(result))])])
        with patch.object(ai,'generate',side_effect=answer) as gemini, patch.object(dubbing,'openai_call') as openai:
            self.store.process(job,dict(openai='gemini-test',stt='whisper-test',ai33='tts-test'),threading.Event())
            self.assertEqual(job['state'],'done',job['message'])
            self.assertTrue(gemini.called);openai.assert_not_called()
            self.assertEqual([(s['start'],s['end']) for s in job['segments']],[(.2,1.4),(2.0,2.9)])
            calls=gemini.call_count
            self.store.process(job,dict(openai='gemini-test',stt='whisper-test',ai33='tts-test'),threading.Event())
            self.assertEqual(gemini.call_count,calls)

class RetryAndCancellationTests(unittest.TestCase):
    def test_retry_after_http_date(self):
        with patch.object(ai.time,'time',return_value=0):
            self.assertEqual(ai.retry_delay({'retry-after':'Thu, 01 Jan 1970 00:00:30 GMT'},0),30)
        self.assertEqual(ai.retry_delay({'retry-after':'12'},0),12)

    def test_cancel_before_request(self):
        event=threading.Event();event.set()
        previous=getattr(ai.CONTEXT,'cancel',None)
        ai.CONTEXT.cancel=event
        try:
            with patch.object(ai,'models',return_value={'models':['m']}), patch.object(ai,'client') as sdk:
                with self.assertRaisesRegex(ai.ProviderError,'hủy'):
                    ai.generate(dict(model='m',input=[],text={'format':{'schema':{}}},max_output_tokens=1),{},1)
                sdk.return_value.__enter__.return_value.models.generate_content.assert_not_called()
        finally:
            ai.CONTEXT.cancel=previous
