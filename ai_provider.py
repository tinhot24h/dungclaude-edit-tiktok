"""Gemini adapter for the existing Responses-shaped structured writing pipeline.

Only model IDs returned by Google's generateContent catalog are accepted.
No prompts, credentials or raw remote errors are persisted in diagnostics.
"""
import base64
import json
import random
import threading
import time
from email.utils import parsedate_to_datetime
from pathlib import Path
import secrets_store

ROOT = Path(__file__).resolve().parent / '.local'
LOCK = threading.RLock()
CONTEXT = threading.local()


class ProviderError(ValueError):
    pass


def client(key, timeout=180):
    if not key:
        raise ProviderError('Chưa có Gemini API key.')
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise ProviderError('Cài Gemini SDK: python -m pip install -r requirements-gemini.txt') from None
    return genai.Client(api_key=key, http_options=types.HttpOptions(
        timeout=int(timeout * 1000), retry_options=types.HttpRetryOptions(attempts=1)))


def read(name, default):
    try:
        return json.loads((ROOT / name).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def write(name, data):
    ROOT.mkdir(exist_ok=True)
    path = ROOT / name
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    tmp.replace(path)


def models(refresh=False):
    with LOCK:
        cached = read('gemini-models.json', {'models': [], 'checked_at': None})
    if not refresh:
        return cached
    try:
        with client(secrets_store.get('gemini'), 30) as sdk:
            found = sorted({m.name.removeprefix('models/') for m in sdk.models.list()
                            if m.name and 'generateContent' in (m.supported_actions or [])})
    except Exception:
        raise ProviderError('Không xác minh được model Gemini. Kiểm tra key, quyền và mạng; danh sách cũ không chứng minh kết nối hiện tại.') from None
    data = {'models': found, 'checked_at': time.time()}
    with LOCK:
        write('gemini-models.json', data)
    return data


def record(model, ok, attempt, usage=None, code=None):
    with LOCK:
        data = read('ai-usage.json', {})
        day = time.strftime('%Y-%m-%d', time.gmtime())
        item = data.setdefault(day, {}).setdefault('gemini/' + model,
            dict(attempts=0, tasks=0, success=0, failed=0, retries=0, rate_limits=0,
                 input_tokens=0, output_tokens=0, total_tokens=0, missing_usage=0))
        item['attempts'] += 1
        item['tasks'] += int(attempt == 0)
        item['retries'] += int(attempt > 0)
        item['success' if ok else 'failed'] += 1
        item['rate_limits'] += int(code == 429)
        item['last_at'] = time.time()
        if usage is None:
            item['missing_usage'] += 1
        else:
            for field, attr in [('input_tokens', 'prompt_token_count'), ('output_tokens', 'candidates_token_count'), ('total_tokens', 'total_token_count')]:
                value = getattr(usage, attr, None)
                if value is not None:
                    item[field] += value
        write('ai-usage.json', data)


def retry_delay(headers, retry):
    value = headers.get('retry-after')
    if value is not None:
        try:
            return max(0, float(value))
        except (TypeError, ValueError):
            try:
                return max(0, parsedate_to_datetime(value).timestamp() - time.time())
            except (TypeError, ValueError, OverflowError):
                pass
    return 2 ** retry + random.random()


def generate(body, settings, timeout):
    try:
        from google.genai import types
    except ImportError:
        raise ProviderError('Cài SDK: python -m pip install -r requirements-gemini.txt') from None
    catalog = models()
    selected = [body['model']]
    if settings.get('fallback_enabled') and settings.get('fallback_model') != body['model']:
        selected.append(settings.get('fallback_model'))
    if any(m not in catalog['models'] for m in selected):
        raise ProviderError('Model Gemini chưa xác minh. Bấm làm mới danh sách và chọn model hỗ trợ generateContent.')
    contents, system = [], []
    for msg in body['input']:
        if msg['role'] == 'developer':
            system.append(msg['content'])
            continue
        parts = []
        content = msg['content']
        for part in ([dict(type='input_text', text=content)] if isinstance(content, str) else content):
            if part['type'] == 'input_text':
                parts.append(types.Part.from_text(text=part['text']))
            elif part['type'] == 'input_image':
                url = part['image_url']
                if not url.startswith('data:image/'):
                    raise ProviderError('Gemini chỉ nhận khung hình nội bộ dạng data URI.')
                header, encoded = url.split(',', 1)
                parts.append(types.Part.from_bytes(data=base64.b64decode(encoded, validate=True), mime_type=header[5:].split(';')[0]))
        contents.append(types.Content(role='user', parts=parts))
    attempt = 0
    with client(secrets_store.get('gemini'), timeout) as sdk:
        for model in selected:
            for retry in range(3):
                cancel = getattr(CONTEXT, "cancel", None)
                if cancel and cancel.is_set():
                    raise ProviderError("Đã hủy yêu cầu Gemini.")
                try:
                    response = sdk.models.generate_content(model=model, contents=contents, config=types.GenerateContentConfig(
                        system_instruction='\n'.join(system), response_mime_type='application/json',
                        response_json_schema=body['text']['format']['schema'], max_output_tokens=body['max_output_tokens']))
                    text = response.text
                    parsed = json.loads(text or '')
                    import jsonschema
                    jsonschema.validate(parsed, body['text']['format']['schema'])
                    if not parsed or any(isinstance(v, str) and not v.strip() for v in parsed.values()):
                        raise ValueError('Empty structured response')
                    record(model, True, attempt, response.usage_metadata)
                    return dict(status='completed', model=model, output=[dict(type='message', content=[dict(type='output_text', text=text)])])
                except Exception as exc:
                    code = getattr(exc, 'code', None)
                    record(model, False, attempt, code=code)
                    attempt += 1
                    import httpx
                    transient = code == 429 or (isinstance(code, int) and 500 <= code < 600) or isinstance(exc, (TimeoutError, ConnectionError, httpx.TransportError))
                    if not transient:
                        raise ProviderError('Gemini từ chối yêu cầu hoặc trả JSON không hợp lệ. Kiểm tra key, model, quyền và schema.') from None
                    if retry < 2:
                        headers = getattr(getattr(exc, 'response', None), 'headers', {})
                        delay = retry_delay(headers, retry)
                        if delay > 60:
                            raise ProviderError('Gemini yêu cầu chờ lâu hơn 60 giây; hãy thử lại sau theo Retry-After.') from None
                        if cancel:
                            if cancel.wait(delay):
                                raise ProviderError("Đã hủy yêu cầu Gemini.") from None
                        else:
                            time.sleep(delay)
    raise ProviderError('Gemini tạm thời không khả dụng sau số lần thử giới hạn; không chuyển sang OpenAI.')
