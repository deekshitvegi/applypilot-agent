@echo off
rem Double-click this ONCE. After that the service starts by itself whenever
rem you sign in, and opening Chrome is the only thing you ever do.
rem
rem It puts a single shortcut in your own Startup folder. Nothing needs
rem administrator and nothing is written outside your own profile.
rem
rem To undo it, run:  scripts\install-autostart.ps1 -Remove

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\install-autostart.ps1"
echo.
pause
