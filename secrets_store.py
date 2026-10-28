"""API keys the user chose to remember on this computer (opt-in, per provider).

Stored in .local/secrets.json (read/write for the current user only where the OS supports it). The folder is never
packed into the ZIP, never uploaded and kept by the updater. The browser only ever gets a masked hint back.
"""
import json
import os
import threading
from pathlib import Path

PROVIDERS = ('openai', 'gemini', 'ai33')
PATH = Path(__file__).resolve().parent / '.local' / 'secrets.json'
LOCK = threading.Lock()


def valid(key):
    return isinstance(key, str) and 8 <= len(key) <= 1024 and all(33 <= ord(c) <= 126 for c in key)


def _read():
    try:
        data = json.loads(PATH.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if k in PROVIDERS and valid(v)} if isinstance(data, dict) else {}


def _write(data):
    PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PATH.with_suffix('.tmp')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as out:
        json.dump(data, out)
    tmp.replace(PATH)
    try:
        os.chmod(PATH, 0o600)
    except OSError:
        pass


def get(provider):
    with LOCK:
        return _read().get(provider, '')


def save(provider, key):
    if provider not in PROVIDERS:
        raise ValueError('Nhà cung cấp không hợp lệ.')
    key = (key or '').strip()
    if not valid(key):
        raise ValueError('API key có định dạng không hợp lệ.')
    with LOCK:
        data = _read()
        data[provider] = key
        _write(data)
    return status()


def delete(provider):
    if provider not in PROVIDERS:
        raise ValueError('Nhà cung cấp không hợp lệ.')
    with LOCK:
        data = _read()
        data.pop(provider, None)
        if data:
            _write(data)
        else:
            PATH.unlink(missing_ok=True)
    return status()


def status():
    with LOCK:
        data = _read()
    return {p: {'saved': p in data, 'hint': ('••••' + data[p][-4:]) if p in data else ''} for p in PROVIDERS}
