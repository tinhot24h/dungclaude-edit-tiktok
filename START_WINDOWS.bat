@echo off
cd /d "%~dp0"
rem Python: "py" launcher, then "python" (the Microsoft Store stub does not count), else install it with winget
call :findpy
if not defined PYCMD (
    echo Chua co Python 3. Dang tu cai Python 3.12 bang winget, vui long doi...
    where winget >nul 2>nul
    if errorlevel 1 (
        echo Khong co winget tren may nay. Cai Python tai https://www.python.org/downloads/ ^(tick "Add Python to PATH"^) roi mo lai.
        pause
        exit /b 1
    )
    winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
    set "PATH=%LocalAppData%\Programs\Python\Python312;%LocalAppData%\Programs\Python\Python312\Scripts;%LocalAppData%\Programs\Python\Launcher;%PATH%"
    call :findpy
)
if not defined PYCMD (
    echo Da cai Python nhung chua nhan. Dong cua so nay va mo lai START_WINDOWS.bat.
    pause
    exit /b 1
)
rem FFmpeg is downloaded by launch.py itself when it is missing
%PYCMD% launch.py
if errorlevel 1 (
    echo.
    echo Xem HUONG_DAN.txt de cai Python va FFmpeg.
    pause
)
exit /b

:findpy
set "PYCMD="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if not errorlevel 1 (
    set "PYCMD=py -3"
    exit /b
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if not errorlevel 1 set "PYCMD=python"
exit /b
