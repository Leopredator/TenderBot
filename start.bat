@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating virtual environment...
    py -3 -m venv .venv
    if errorlevel 1 goto :error
    echo [2/3] Installing dependencies...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    if errorlevel 1 goto :error
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto :error
)

echo [3/3] Starting TenderBot...
".venv\Scripts\python.exe" run.py
pause
exit /b 0

:error
echo.
echo Setup failed. Make sure Python 3.10+ is installed: py -3 --version
echo Then try again.
pause
exit /b 1