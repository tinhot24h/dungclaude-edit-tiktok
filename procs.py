"""Child processes of the app (FFmpeg, FFprobe, Demucs, pip…) end with it.

- track(): every subprocess the app starts is remembered, so quitting (⏻, an update restart) stops the ones still
  running instead of leaving FFmpeg exports or Demucs running in the background (Windows does not end the children
  of a process that exits).
- bind(process): Windows only. The launcher puts the app's process in a job object that kills everything in it when
  the launcher ends, so closing the black window, Ctrl+C or a crash never leaves an FFmpeg behind either. The browser
  is opened by the launcher itself, outside the job, so it is never closed with the app.
"""
import os
import subprocess
import threading
import weakref

_live = weakref.WeakSet()
_lock = threading.Lock()
_init = subprocess.Popen.__init__
_jobs = []                      # job handles stay open as long as the launcher runs
KEEP = ('explorer', 'explorer.exe', 'open', 'xdg-open')   # "Mở thư mục" windows are the user's, not ours
BREAKAWAY = 0x01000000          # CREATE_BREAKAWAY_FROM_JOB


def _tracked(self, *args, **kwargs):
    _init(self, *args, **kwargs)
    with _lock:
        _live.add(self)


def track():
    if subprocess.Popen.__init__ is not _tracked:
        subprocess.Popen.__init__ = _tracked


def running():
    with _lock:
        procs = list(_live)
    out = []
    for p in procs:
        try:
            name = os.path.basename(str(p.args[0] if isinstance(p.args, (list, tuple)) else p.args).split()[0]).lower()
        except (IndexError, TypeError):
            name = ''
        if p.poll() is None and name not in KEEP:
            out.append(p)
    return out


def stop_all(wait=3.0):
    """Kill every child still running (with its own children on Windows). Returns how many were stopped."""
    procs = running()
    for p in procs:
        try:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(p.pid)], capture_output=True, timeout=10,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if p.poll() is None:
                p.kill()
        except (OSError, subprocess.SubprocessError):
            pass
    for p in procs:
        try:
            p.wait(timeout=wait)
        except (OSError, subprocess.SubprocessError):
            pass
    return len(procs)


def popen_outside(cmd, **kwargs):
    """Start a program that must outlive the app (a folder window): outside the job when the job allows it."""
    if os.name == 'nt':
        try:
            return subprocess.Popen(cmd, creationflags=BREAKAWAY, **kwargs)
        except OSError:
            pass
    return subprocess.Popen(cmd, **kwargs)


def bind(process):
    """Windows: put `process` (and so everything it starts later) in a job that is killed when this process ends."""
    if os.name != 'nt':
        return False
    try:
        import ctypes
        from ctypes import wintypes

        class IO(ctypes.Structure):
            _fields_ = [(n, ctypes.c_ulonglong) for n in ('ro', 'wo', 'oo', 'rb', 'wb', 'ob')]

        class Basic(ctypes.Structure):
            _fields_ = [('user_time', ctypes.c_int64), ('job_time', ctypes.c_int64), ('flags', wintypes.DWORD),
                        ('min_ws', ctypes.c_size_t), ('max_ws', ctypes.c_size_t), ('processes', wintypes.DWORD),
                        ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD), ('scheduling', wintypes.DWORD)]

        class Extended(ctypes.Structure):
            _fields_ = [('basic', Basic), ('io', IO), ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                        ('peak_process', ctypes.c_size_t), ('peak_job', ctypes.c_size_t)]

        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
        kernel.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
        kernel.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
        job = kernel.CreateJobObjectW(None, None)
        if not job:
            return False
        info = Extended()
        info.basic.flags = 0x2000 | 0x800     # KILL_ON_JOB_CLOSE | BREAKAWAY_OK (folder windows may leave)
        if not kernel.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
            return False
        if not kernel.AssignProcessToJobObject(job, wintypes.HANDLE(int(process._handle))):
            return False
        _jobs.append(job)
        return True
    except (OSError, AttributeError, ValueError):
        return False
