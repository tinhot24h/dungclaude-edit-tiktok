"""Where finished videos are saved on this computer, plus native folder picking/opening."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

LOCK=threading.Lock()
PICKER='''import sys
sys.stdout.reconfigure(encoding="utf-8")
import tkinter as tk
from tkinter import filedialog
root=tk.Tk();root.withdraw();root.attributes("-topmost",True)
print(filedialog.askdirectory(initialdir=sys.argv[1],title=sys.argv[2] if len(sys.argv)>2 else "Chọn thư mục lưu video xuất") or "")
'''


def default_dir():
    home=Path.home()
    videos=home/'Videos' if (home/'Videos').is_dir() else home/'Movies' if (home/'Movies').is_dir() else home
    return videos/'ReviewStudio'


def load(path):
    try:data=json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError,ValueError):data={}
    data=data if isinstance(data,dict) else {}
    folder=data.get('output_dir') if isinstance(data.get('output_dir'),str) and data.get('output_dir') else str(default_dir())
    return dict(output_dir=folder,auto_save=data.get('auto_save',True) is not False,default_dir=str(default_dir()))


def check_dir(value):
    """Create the folder if needed and prove it is writable; raises ValueError with a user-facing message."""
    if not isinstance(value,str) or not value.strip() or len(value)>1000 or '\x00' in value:raise ValueError('Đường dẫn thư mục không hợp lệ.')
    folder=Path(os.path.expandvars(value.strip())).expanduser()
    if not folder.is_absolute():raise ValueError('Nhập đường dẫn đầy đủ, ví dụ D:\\Video\\TikTok hoặc /Users/ban/Movies.')
    try:
        folder.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=folder,prefix='.reviewstudio-',delete=True):pass
    except OSError:raise ValueError('Không ghi được vào thư mục này. Chọn thư mục khác hoặc kiểm tra quyền ghi.') from None
    return folder


def save(path,raw):
    if not isinstance(raw,dict):raise ValueError('Cài đặt không hợp lệ.')
    current=load(path)
    if 'auto_save' in raw:
        if not isinstance(raw['auto_save'],bool):raise ValueError('Cài đặt tự lưu không hợp lệ.')
        current['auto_save']=raw['auto_save']
    if 'output_dir' in raw:current['output_dir']=str(check_dir(raw['output_dir']))
    with LOCK:
        tmp=Path(path).with_suffix('.tmp');tmp.write_text(json.dumps({k:current[k] for k in ('output_dir','auto_save')},ensure_ascii=False),encoding='utf-8');tmp.replace(path)
    return load(path)


def clean(name):
    return ''.join('_' if c in '<>:"/\\|?*' or ord(c)<32 else c for c in name).strip(' .') or 'review-video'


def unique(folder,name,alts=()):
    stem=clean(name)
    if not (folder/(stem+'.mp4')).exists():return folder/(stem+'.mp4')
    # the AI's second name is used before numbering: vay-maxi-hoa-nhi taken → vay-maxi-di-bien, then vay-maxi-hoa-nhi-2…
    for alt in alts:
        if alt and not (folder/(clean(alt)+'.mp4')).exists():return folder/(clean(alt)+'.mp4')
    # a name the AI gave (quan-ao-nu-hottrend) gets -2, -3…; other names " (2)", " (3)"… — an existing file is never overwritten
    slug='-' in stem and all(c.islower() or c.isdigit() or c=='-' for c in stem)
    target=folder/(stem+'.mp4');index=2
    while target.exists():target=folder/(f'{stem}-{index}.mp4' if slug else f'{stem} ({index}).mp4');index+=1
    return target


def deliver(path,source,name,alts=()):
    """Put a finished MP4 into the chosen folder without overwriting older exports (hard link when possible)."""
    settings=load(path)
    folder=check_dir(settings['output_dir'])
    with LOCK:
        target=unique(folder,name,alts)
        partial=target.with_name('.'+target.name+'.part')
        try:
            # same drive: a hard link (the file is stored once); another drive: a copy
            try:os.link(source,partial)
            except OSError:shutil.copyfile(source,partial)
            partial.replace(target)
        except OSError:
            partial.unlink(missing_ok=True)
            raise ValueError('Không chép được video vào thư mục đã chọn (đầy ổ đĩa hoặc không có quyền ghi). Vẫn có thể tải về.') from None
    return target


FILE_PICKER='''import json,sys
sys.stdout.reconfigure(encoding="utf-8")
import tkinter as tk
from tkinter import filedialog
root=tk.Tk();root.withdraw();root.attributes("-topmost",True)
types=json.loads(sys.argv[3])
ask=filedialog.askopenfilenames if sys.argv[2]=="1" else filedialog.askopenfilename
got=ask(title=sys.argv[1],filetypes=[(name,pattern) for name,pattern in types]+[("Tất cả file","*.*")])
got=[got] if isinstance(got,str) else list(got or [])
print(json.dumps([g for g in got if g]))
'''


def pick_files(title,types,multiple=True):
    """Native file dialog (child process, like pick): returns the chosen paths on this computer."""
    try:
        run=subprocess.run([sys.executable,'-c',FILE_PICKER,title,'1' if multiple else '0',json.dumps(types)],capture_output=True,timeout=900)
    except (OSError,subprocess.SubprocessError):
        raise ValueError('Không mở được hộp chọn file.') from None
    if run.returncode:raise ValueError('Máy này chưa có hộp chọn file (tkinter).')
    try:return [p for p in json.loads(run.stdout.decode('utf-8','replace').strip() or '[]') if isinstance(p,str)]
    except ValueError:return []


def pick(initial,title='Chọn thư mục lưu video xuất'):
    """Native folder dialog in a child process (Tk must own its own main thread)."""
    try:
        run=subprocess.run([sys.executable,'-c',PICKER,initial,title],capture_output=True,timeout=600)
    except (OSError,subprocess.SubprocessError):
        raise ValueError('Không mở được hộp chọn thư mục. Hãy dán đường dẫn vào ô thư mục.') from None
    if run.returncode:raise ValueError('Máy này chưa có hộp chọn thư mục (tkinter). Hãy dán đường dẫn vào ô thư mục.')
    return run.stdout.decode('utf-8','replace').strip()


def reveal(target):
    """Open the folder (selecting the file when possible) in the system file manager."""
    target=Path(target)
    if not target.exists():raise ValueError('Thư mục hoặc file không còn tồn tại.')
    try:
        if sys.platform=='win32':
            subprocess.Popen(['explorer','/select,',str(target)] if target.is_file() else ['explorer',str(target)])
        elif sys.platform=='darwin':
            subprocess.Popen(['open','-R',str(target)] if target.is_file() else ['open',str(target)])
        else:
            subprocess.Popen(['xdg-open',str(target.parent if target.is_file() else target)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    except OSError:raise ValueError('Không mở được trình quản lý file trên máy này.') from None
