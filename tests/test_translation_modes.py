import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
import ai_translate as ai

RESULT=dict(literal='Khăn này dùng cho nhà bếp.',script='Đây là chiếc khăn dùng để vệ sinh trong nhà bếp.',notes=[])


def response(result=RESULT,finish='STOP'):
    return dict(candidates=[dict(finishReason=finish,content=dict(parts=[dict(text=json.dumps(result))]))])


class TranslationModeTests(unittest.TestCase):
    def source(self,**options):
        data=dict(source='这条毛巾适用于厨房。',style='review',tone='friendly',duration=30,pronoun='neutral',provider='gemini')
        data.update(options)
        return data

    def test_gemini_request_uses_own_host_header_and_schema(self):
        captured=[]
        def provider(req,timeout):
            captured.append(req)
            return io.BytesIO(json.dumps(response()).encode())
        with patch.dict(ai.os.environ,{},clear=True),patch.object(ai.request,'urlopen',side_effect=provider):
            result=ai.translate(self.source(api_key='gemini-dummy-key'))
        self.assertEqual(result['provider'],'gemini')
        self.assertEqual(result['script'],RESULT['script'])
        req=captured[0]
        self.assertEqual(req.full_url,ai.GEMINI_ROOT+'gemini-2.5-flash:generateContent')
        self.assertEqual(req.get_header('X-goog-api-key'),'gemini-dummy-key')
        self.assertIsNone(req.get_header('Authorization'))
        self.assertNotIn('gemini-dummy-key',req.full_url+req.data.decode())
        data=json.loads(req.data)
        self.assertEqual(data['generationConfig']['responseMimeType'],'application/json')
        self.assertEqual(data['generationConfig']['responseSchema']['type'],'OBJECT')
        self.assertEqual(json.loads(data['contents'][0]['parts'][0]['text'])['source'],self.source()['source'])

    def test_provider_keys_are_not_substituted(self):
        with patch.dict(ai.os.environ,{'OPENAI_API_KEY':'openai-dummy-key'},clear=True),patch.object(ai.request,'urlopen') as call:
            with self.assertRaises(ai.AIError) as result:ai.translate(self.source())
            self.assertIn('Gemini',str(result.exception))
            call.assert_not_called()
        with patch.dict(ai.os.environ,{'GOOGLE_API_KEY':'google-dummy-key','OPENAI_API_KEY':'openai-dummy-key'},clear=True),patch.object(ai.request,'urlopen',return_value=io.BytesIO(json.dumps(response()).encode())) as call:
            ai.translate(self.source())
            self.assertEqual(call.call_args.args[0].get_header('X-goog-api-key'),'google-dummy-key')

    def test_gemini_quota_does_not_fall_back_or_retry(self):
        failure=HTTPError(ai.GEMINI_ROOT,429,'secret vendor text',{},io.BytesIO(b'gemini-dummy-key'))
        with patch.object(ai.request,'urlopen',side_effect=failure) as call,self.assertRaises(ai.AIError) as result:
            ai.translate(self.source(api_key='gemini-dummy-key'))
        self.assertEqual(call.call_count,1)
        self.assertEqual(result.exception.status,429)
        self.assertIn('thủ công',str(result.exception))
        self.assertNotIn('gemini-dummy-key',str(result.exception))

    def test_manual_prompt_needs_no_key_and_never_calls_provider(self):
        with patch.object(ai.request,'urlopen') as call:
            prompt=ai.manual_prompt(self.source(api_key='do-not-copy-this-key'))
            self.assertIn(self.source()['source'],prompt)
            self.assertNotIn('do-not-copy-this-key',prompt)
            self.assertIn('literal',prompt)
            call.assert_not_called()
            with self.assertRaises(ai.AIError):ai.translate(self.source(provider='manual'))
            call.assert_not_called()

    def test_manual_json_import_supports_code_fences(self):
        with patch.object(ai.request,'urlopen') as call:
            for fence in ('','```json\n','```JSON\n'):
                text=fence+json.dumps(RESULT,ensure_ascii=False)+('\n```' if fence else '')
                result=ai.import_manual(dict(text=text))
                self.assertEqual(result['script'],RESULT['script'])
                self.assertEqual(result['provider'],'manual')
            call.assert_not_called()
        for text in ('not json','{"script":"x"}',json.dumps(dict(literal='x',script='y',notes='bad'))):
            with self.assertRaises(ValueError):ai.import_manual(dict(text=text))

    def test_gemini_incomplete_or_blocked_response_rejected(self):
        for raw in (response(finish='MAX_TOKENS'),dict(promptFeedback=dict(blockReason='SAFETY')),dict(candidates=[])):
            with self.assertRaises(ai.AIError):ai.parse_gemini(raw)

    def test_model_path_and_provider_validation(self):
        self.assertEqual(ai.parameters(self.source(model='models/gemini-2.5-flash'))['model'],'gemini-2.5-flash')
        for options in (dict(model='../secret'),dict(provider='unknown')):
            with self.assertRaises(ValueError):ai.parameters(self.source(**options))


if __name__=='__main__':unittest.main()


class VideoTextTests(unittest.TestCase):
    def test_prompt_asks_for_title_and_body_sized_to_the_boxes(self):
        prompt=ai.manual_prompt(dict(source='这款香薰很好用',layout=dict(title_font='sans-bold',title_size=40,title_width=400,body_font='sans',body_size=22,body_width=548)))
        config=json.loads(prompt[prompt.index('{',prompt.index('CẤU HÌNH')):prompt.rindex('}')+1])
        self.assertIn('title, body',prompt)
        self.assertLess(config['video_text']['title_max_chars'],ai.capacity(ai.fit_layout({}))['title']['max_chars'])
        self.assertEqual(config['video_text']['body_max_lines'],5)
        self.assertNotIn('layout',config)
        with self.assertRaises(ValueError):ai.manual_prompt(dict(source='x',layout=dict(title_font='comic')))
        schema=ai.payload(ai.parameters(dict(source='x',provider='openai')))['text']['format']['schema']
        self.assertEqual(schema['required'],['literal','script','title','body','notes'])

    def test_import_keeps_title_body_and_warns_on_overflow(self):
        text=json.dumps({**RESULT,'title':'  Tinh dầu   thơm phòng ','body':'Mùi dịu nhẹ.\n\nDùng cho phòng ngủ.'})
        result=ai.import_manual(dict(text=text))
        self.assertEqual((result['title'],result['body']),('Tinh dầu thơm phòng','Mùi dịu nhẹ.\nDùng cho phòng ngủ.'))
        self.assertEqual(result['fit']['title']['lines'],1);self.assertEqual(result['notes'],[])
        long=ai.import_manual(dict(text=json.dumps({**RESULT,'title':'TIÊU ĐỀ RẤT DÀI '*8,'body':''})))
        self.assertTrue(any('Tiêu đề dài' in n for n in long['notes']))
        old=ai.import_manual(dict(text=json.dumps(RESULT)))
        self.assertEqual((old['title'],old['body']),('',''))
