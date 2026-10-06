@echo off
setlocal
cd /d "%~dp0"
title TriCue - Snooker Scoreboard

echo ==========================================
echo              TRICUE
echo       Snooker Scoreboard
echo ==========================================
echo.

set "PY="
where py >nul 2>&1 && set "PY=py"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY (
  echo Python was not found. Install Python 3.10+ first.
  pause
  exit /b 1
)

%PY% -c "import flask" >nul 2>&1
if errorlevel 1 (
  echo Installing Flask...
  %PY% -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Flask installation failed.
    pause
    exit /b 1
  )
)

echo Starting TriCue...
start "TriCue Server" /b %PY% app.py
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:5000/"
echo.
echo TriCue is running at http://127.0.0.1:5000/
echo Keep this window open while using TriCue.
pause
