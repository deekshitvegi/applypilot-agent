@echo off
rem Double-click this to start the local service. Nothing else needed.
rem
rem It uses pythonw, so no window stays open and nothing sits in the taskbar.
rem The service listens on 127.0.0.1 only. Close it from Task Manager, or just
rem sign out.

cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
  echo No .venv here yet.
  echo Run scripts\setup.ps1 first, then try again.
  pause
  exit /b 1
)

rem Already answering? Then there is nothing to do.
curl -s -o nul --max-time 3 http://127.0.0.1:8765/health 2>nul
if not errorlevel 1 (
  echo ApplyPilot is already running.
  ping -n 3 127.0.0.1 >nul
  exit /b 0
)

start "" ".venv\Scripts\pythonw.exe" -m applypilot --port 8765
echo Starting ApplyPilot... open the side panel in Chrome.
ping -n 4 127.0.0.1 >nul
