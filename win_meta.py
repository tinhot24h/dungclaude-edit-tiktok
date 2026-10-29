"""Windows-only file properties of an exported MP4 (Explorer → Properties → Details): Tags, Rating, Authors,
Directors, Producers, Writers, Publisher, Author URL, Promotion URL, Copyright. FFmpeg cannot write these where
Windows reads them, so the Windows property system does it, through pywin32 (installed once on first use).

The writer runs in a separate Python process: a fresh interpreter sees a just-installed pywin32, and a COM
failure can never take the app down. On other systems nothing is written and the export is unaffected."""
import json
import os
import subprocess
import sys
import tempfile
import threading

LOCK = threading.Lock()
_state = {}
# Windows rating scale for 1–5 stars
STARS = {1: 1, 2: 25, 3: 50, 4: 75, 5: 99}
KEYS = dict(title='System.Title', keywords='System.Keywords', rating='System.Rating', authors='System.Author',
            directors='System.Video.Director', producers='System.Media.Producer', writers='System.Media.Writer',
            publisher='System.Media.Publisher', author_url='System.Media.AuthorUrl', promotion_url='System.Media.PromotionUrl',
            copyright='System.Copyright')
LISTS = ('keywords', 'authors', 'directors', 'producers', 'writers')


def flags():
    return subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0


def ready():
    """pywin32 importable; tries `pip install pywin32` once per run of the app."""
    if os.name != 'nt':
        return False
    with LOCK:
        if 'ok' not in _state:
            check = [sys.executable, '-c', 'import pythoncom; from win32com.propsys import propsys']
            ok = subprocess.run(check, capture_output=True, creationflags=flags(), timeout=60).returncode == 0
            if not ok:
                try:
                    subprocess.run([sys.executable, '-m', 'pip', 'install', 'pywin32', '--quiet', '--disable-pip-version-check'],
                                   capture_output=True, creationflags=flags(), timeout=600)
                except (OSError, subprocess.SubprocessError):
                    pass
                ok = subprocess.run(check, capture_output=True, creationflags=flags(), timeout=60).returncode == 0
            _state['ok'] = ok
        return _state['ok']


def write(path, props):
    """Write the properties; returns None when done (or nothing to do) and a short message otherwise."""
    if not props:
        return None
    if os.name != 'nt':
        return None
    try:
        if not ready():
            return 'chưa cài được pywin32 (cần Internet lần đầu) nên Tags, đánh giá, link kênh chưa ghi được; tiêu đề và tác giả vẫn có.'
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(dict(path=os.path.abspath(str(path)), props=props), f, ensure_ascii=False)
        try:
            done = subprocess.run([sys.executable, os.path.abspath(__file__), f.name], capture_output=True, text=True, encoding='utf-8',
                                  errors='replace', creationflags=flags(), timeout=120)
        finally:
            os.unlink(f.name)
        if done.returncode:
            return 'Windows không ghi được Tags / đánh giá / link kênh (' + (done.stdout or done.stderr).strip()[-160:] + ').'
    except (OSError, subprocess.SubprocessError) as exc:
        return 'Windows không ghi được Tags / đánh giá / link kênh (' + str(exc)[:160] + ').'
    return None


def main(job_file):
    import pythoncom
    from win32com.propsys import propsys, pscon
    with open(job_file, encoding='utf-8') as f:
        job = json.load(f)
    pythoncom.CoInitialize()
    try:
        store = propsys.SHGetPropertyStoreFromParsingName(job['path'], None, pscon.GPS_READWRITE, propsys.IID_IPropertyStore)
        for name, value in job['props'].items():
            key = propsys.PSGetPropertyKeyFromName(KEYS[name])
            if name in LISTS:
                variant = propsys.PROPVARIANTType([str(v) for v in value], pythoncom.VT_VECTOR | pythoncom.VT_BSTR)
            elif name == 'rating':
                variant = propsys.PROPVARIANTType(STARS[int(value)], pythoncom.VT_UI4)
            else:
                variant = propsys.PROPVARIANTType(str(value), pythoncom.VT_BSTR)
            store.SetValue(key, variant)
        store.Commit()
    finally:
        pythoncom.CoUninitialize()


if __name__ == '__main__':
    try:
        main(sys.argv[1])
    except Exception as exc:   # reported back to the app as one line
        print(type(exc).__name__ + ': ' + str(exc))
        sys.exit(1)
