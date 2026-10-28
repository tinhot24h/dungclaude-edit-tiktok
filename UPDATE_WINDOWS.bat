@echo off
cd /d "%~dp0"
echo Cap nhat Review Studio tu GitHub (chi tai cac file thay doi)...
where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3 update.py
) else (
    python update.py
)
echo.
pause
