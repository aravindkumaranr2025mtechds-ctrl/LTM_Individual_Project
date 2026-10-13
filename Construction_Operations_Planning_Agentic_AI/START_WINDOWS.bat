@echo off
setlocal
cd /d "%~dp0"
echo Starting BuildPlan...
where py >nul 2>nul
if not errorlevel 1 (
    py -3 run.py
    goto end
)
where python >nul 2>nul
if not errorlevel 1 (
    python run.py
    goto end
)
echo Python was not found. Install Python 3.11 or newer and enable Add Python to PATH.
:end
pause
