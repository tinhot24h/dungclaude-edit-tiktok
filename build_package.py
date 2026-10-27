"""Build clean portable ZIPs; excludes uploads, credentials and generated jobs."""
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parent
FILES = ['media_bin.js', 'studio_shell.js', 'clip_ui.js', 'output_folder.py', 'library_store.py', 'history_ui.js', 'workspace_ui.js', 'media_preview.py', 'timeline_ui.js', 'tests/test_editor_controls.py', 'asset_store.py', 'media_engine.py', 'editor_ui.js', 'tests/test_media_engine.py', 'app.py', 'ai33_audio.py', 'audio_files.py', 'audio_ui.js', 'ai_translate.py', 'studio.css', 'studio.js', 'ai_ui.js', 'design.py', 'fonts.py', 'index.html', 'launch.py', 'build_package.py',
         'START_WINDOWS.bat', 'START_MAC_LINUX.command', 'HUONG_DAN.txt',
         'README.md', 'VERSION', '.gitignore', 'tests/test_storage.py', 'tests/test_design.py', 'tests/test_ai_translate.py', 'tests/test_translation_modes.py', 'tests/test_ai33_audio.py', 'tests/test_audio_cache.py', 'docs/ai33-api.md',
         'assets/DejaVuSans.ttf', 'assets/DejaVuSans-Bold.ttf',
         'assets/DejaVuSerif.ttf', 'assets/DejaVuSerif-Bold.ttf',
         'assets/DejaVuSansMono.ttf', 'assets/DejaVuSansMono-Bold.ttf', 'assets/FONT_LICENSE.txt']

if __name__ == '__main__':
    output = ROOT / f"ReviewStudio-v{(ROOT / 'VERSION').read_text(encoding='utf-8').strip()}.zip"
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as package:
        for name in FILES:
            package.write(ROOT / name, 'ReviewStudio/'+name)
    with zipfile.ZipFile(output) as package:
        assert package.testzip() is None
    shutil.copyfile(output, ROOT / 'ReviewStudio.zip')
    print(f'Created {output.name} and ReviewStudio.zip ({output.stat().st_size} bytes each)')
