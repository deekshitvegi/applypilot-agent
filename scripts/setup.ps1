# One-time setup on Windows.
#
#   .\scripts\setup.ps1
#
# Creates the virtual environment, installs everything, and fetches the headless
# browser the tests drive.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = "python"
$pinned = "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe"
if (Test-Path $pinned) { $python = $pinned }

if (-not (Test-Path ".venv")) {
    Write-Host "Creating .venv with $python"
    & $python -m venv .venv
}

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    throw ".venv exists but has no interpreter. Delete the .venv folder and run this again."
}

Write-Host "Installing ApplyPilot and its development tools"
& $venvPython -m pip install --upgrade pip --quiet
& $venvPython -m pip install -e ".[dev]"

Write-Host "Installing headless Chromium for the browser tests"
& $venvPython -m playwright install chromium

Write-Host ""
Write-Host "Done. Next:"
Write-Host "  1. .\scripts\start.ps1                      start the local service"
Write-Host "  2. chrome://extensions -> Developer mode -> Load unpacked -> the extension folder"
Write-Host "  3. Open the side panel and work through the setup questions"
