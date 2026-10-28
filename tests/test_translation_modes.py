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
            self.assertIn('hook_options',prompt)
            self.assertNotIn('literal',prompt)
            self.assertIn('tuyệt đối không nhắc giá bán chính xác',prompt)
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
        for text in ('not json','{"script":""}',json.dumps(dict(script='y',hook_options='bad'))):
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
        self.assertEqual(config['video_text']['title_max_chars'],30);self.assertEqual(config['video_text']['title_targets'],[18,24,28])
        small=ai.manual_prompt(dict(source='x',title_chars=20,body_min_chars=40,body_max_chars=80,title_style='question',hint='tinh dầu'))
        small=json.loads(small[small.index('{',small.index('CẤU HÌNH')):small.rindex('}')+1])
        self.assertEqual((small['video_text']['title_max_chars'],small['video_text']['body_max_chars'],small['hint']),(20,80,'tinh dầu'))
        self.assertNotIn('layout',config)
        with self.assertRaises(ValueError):ai.manual_prompt(dict(source='x',layout=dict(title_font='comic')))
        schema=ai.payload(ai.parameters(dict(source='x',provider='openai')))['text']['format']['schema']
        self.assertEqual(schema['required'],list(ai.OUTPUT_FIELDS))

    def test_import_keeps_title_body_and_warns_on_overflow(self):
        text=json.dumps({**RESULT,'title':'  Tinh dầu   thơm phòng ','body':'Mùi dịu nhẹ.\n\nDùng cho phòng ngủ.'})
        result=ai.import_manual(dict(text=text,body_min_chars=0))
        self.assertEqual((result['title'],result['body']),('Tinh dầu thơm phòng','Mùi dịu nhẹ.\nDùng cho phòng ngủ.'))
        self.assertEqual(result['fit']['title']['lines'],1);self.assertEqual(result['warnings'],[]);self.assertNotIn('notes',result)
        long=ai.import_manual(dict(text=json.dumps({**RESULT,'title':'TIÊU ĐỀ RẤT DÀI '*8,'body':''})))
        self.assertTrue(any('Tiêu đề: không phương án nào vừa 30' in n for n in long['warnings']));self.assertLessEqual(len(long['title']),30)
        old=ai.import_manual(dict(text=json.dumps(RESULT)))
        self.assertEqual((old['title'],old['body']),('',''))

    def test_hook_follows_style_and_options_are_deduplicated(self):
        news=ai.manual_prompt(dict(source='x',style='news'));tips=ai.manual_prompt(dict(source='x',style='tips'))
        self.assertIn(ai.HOOKS['news'],news);self.assertIn(ai.HOOKS['tips'],tips);self.assertNotIn(ai.HOOKS['news'],tips)
        self.assertIn('script phải bắt đầu bằng đúng câu hook',news)
        result=ai.import_manual(dict(text=json.dumps({**RESULT,'hook':' Bếp  bẩn mấy cũng sạch? ','hook_options':['Bếp bẩn mấy cũng sạch?','Chỉ 3 giây lau sạch','','Ai cũng cần']})))
        self.assertEqual(result['hook'],'Bếp bẩn mấy cũng sạch?')
        self.assertEqual(result['hook_options'],['Bếp bẩn mấy cũng sạch?','Chỉ 3 giây lau sạch','Ai cũng cần'])
        with self.assertRaises(ValueError):ai.import_manual(dict(text=json.dumps({**RESULT,'hook_options':'x'})))
        self.assertEqual(ai.import_manual(dict(text=json.dumps(RESULT)))['hook_options'],[])


class CustomPromptTests(unittest.TestCase):
    def test_custom_rules_replace_defaults_but_guard_and_contract_stay(self):
        prompt=ai.manual_prompt(dict(source='产品很好',instructions='Viết thật vui, xưng "tui".'))
        self.assertIn('Viết thật vui, xưng "tui".',prompt)
        self.assertNotIn(ai.DEFAULT_RULES[:40],prompt)
        self.assertTrue(prompt.startswith(ai.GUARD))
        self.assertIn(ai.CONTRACT,prompt)
        self.assertIn(ai.DEFAULT_RULES,ai.manual_prompt(dict(source='x',instructions='   ')))
        with self.assertRaises(ValueError):ai.manual_prompt(dict(source='x',instructions='a'*(ai.MAX_RULES+1)))
        with self.assertRaises(ValueError):ai.manual_prompt(dict(source='x',instructions=['bad']))
        params=ai.parameters(dict(source='x',provider='openai',instructions='Quy tắc riêng'))
        self.assertIn('Quy tắc riêng',ai.payload(params)['input'][0]['content'])
        self.assertNotIn('rules',json.loads(ai.payload(params)['input'][1]['content']))

    def test_concrete_prices_are_flagged(self):
        result=ai.import_manual(dict(text=json.dumps(dict(script='Chỉ 99k là có ngay.',hook='Giá mềm bất ngờ?',title='GIÁ 150.000Đ',body='Đang có ưu đãi.'))))
        labels=' '.join(result['warnings'])
        self.assertIn('Kịch bản',labels);self.assertIn('Tiêu đề',labels);self.assertNotIn('Hook',labels);self.assertNotIn('Nội dung video có thể',labels)


class LooseImportTests(unittest.TestCase):
    def test_chat_answers_with_fences_text_newlines_and_smart_quotes_import(self):
        from ai_translate import import_manual
        fenced='Đây là kết quả:\n```json\n{"hook":"A","hook_options":["B"],"script":"dòng 1\ndòng 2","title":"T","body":"X",}\n```\nChúc bạn thành công!'
        result=import_manual(dict(text=fenced))
        self.assertEqual((result['script'],result['title'],result['hook_options']),('dòng 1\ndòng 2','T',['A','B']))
        self.assertEqual(import_manual(dict(text='{“hook”: “A”, “script”: “S”, “title”: “T”, “body”: “B”}'))['body'],'B')
        with self.assertRaises(ValueError):import_manual(dict(text='không có JSON nào'))
