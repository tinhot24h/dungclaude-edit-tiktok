"""Build clean portable ZIPs and MANIFEST.json (used by update.py); excludes uploads, credentials and jobs.

    python build_package.py              write MANIFEST.json and the ZIP
    python build_package.py --manifest   only refresh MANIFEST.json (commit it with every release)
"""
from pathlib import Path
import hashlib
import json
import re
import shutil
import sys
import zipfile
from fonts import FONTS

ROOT = Path(__file__).resolve().parent
FILES = ['tests/test_cost.py', 'tests/test_run_mode.py', 'procs.py', 'tests/test_procs.py', 'ffmpeg_setup.py', 'system_check.py', 'system_ui.js', 'tests/test_system_check.py', 'compat.js', 'video_tools.js', 'tests/test_batch.py', 'win_meta.py', 'ai_texts.py', 'tests/test_ai_texts.py', 'design_tab.js', 'local_files.js', 'demucs_runner.py', 'update.py', 'UPDATE_WINDOWS.bat', 'tests/test_update.py', 'update_ui.js', 'dub_ui.js', 'key_ui.js', 'secrets_store.py', 'dubbing.py', 'tests/test_dubbing.py', 'MANIFEST.json', 'image_ui.js', 'export_ui.js', 'output_folder.py', 'library_store.py', 'history_ui.js', 'media_preview.py', 'tests/test_editor_controls.py', 'asset_store.py', 'media_engine.py', 'editor_ui.js', 'tests/test_media_engine.py', 'app.py', 'ai33_audio.py', 'audio_files.py', 'audio_ui.js', 'ai_translate.py', 'studio.css', 'studio.js', 'design.py', 'fonts.py', 'index.html', 'launch.py', 'build_package.py',
         'START_WINDOWS.bat', 'HUONG_DAN.txt',
         'README.md', 'VERSION', '.gitignore', 'tests/test_storage.py', 'tests/test_design.py', 'tests/test_ai33_audio.py', 'tests/test_audio_cache.py', 'docs/ai33-api.md',
         'assets/DejaVuSans.ttf', 'assets/DejaVuSans-Bold.ttf',
         'assets/DejaVuSerif.ttf', 'assets/DejaVuSerif-Bold.ttf',
         'assets/DejaVuSansMono.ttf', 'assets/DejaVuSansMono-Bold.ttf', 'assets/FONT_LICENSE.txt', 'assets/FONT_LICENSE_OFL.txt']
FILES += sorted({'assets/' + f for f, _, _ in FONTS.values()} - set(FILES))   # every bundled font



def notes():
    """The newest "Mới trong …" section of the README, shown by the in-app updater."""
    text = (ROOT / 'README.md').read_text(encoding='utf-8')
    match = re.search(r'^## Mới trong .*?(?=^## )', text, flags=re.M | re.S)
    return match[0].strip()[:4000] if match else ''


def write_manifest():
    files = {}
    for name in FILES:
        if name == 'MANIFEST.json':
            continue
        data = (ROOT / name).read_bytes()
        files[name] = {'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)}
    body = {'app': 'ReviewStudio', 'version': (ROOT / 'VERSION').read_text(encoding='utf-8').strip(), 'notes': notes(), 'files': files}
    (ROOT / 'MANIFEST.json').write_text(json.dumps(body, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return body


if __name__ == '__main__':
    write_manifest()
    if '--manifest' in sys.argv:
        print('MANIFEST.json updated')
        sys.exit(0)
    output = ROOT / f"ReviewStudio-v{(ROOT / 'VERSION').read_text(encoding='utf-8').strip()}.zip"
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as package:
        for name in FILES:
            package.write(ROOT / name, 'ReviewStudio/'+name)
    with zipfile.ZipFile(output) as package:
        assert package.testzip() is None
    shutil.copyfile(output, ROOT / 'ReviewStudio.zip')
    print(f'Created {output.name} and ReviewStudio.zip ({output.stat().st_size} bytes each)')
