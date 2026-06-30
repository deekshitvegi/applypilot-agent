$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root

if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
    throw "ApplyPilot is not set up. Run .\scripts\setup.ps1 first."
}

& ".venv\Scripts\python.exe" -m uvicorn applypilot.main:app --host 127.0.0.1 --port 8765
