$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$ollama = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"

if ((Test-Path -LiteralPath $ollama) -and
    -not (Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden
}

if (-not (Test-Path -LiteralPath $python)) {
    throw "ApplyPilot is not set up. Run .\scripts\setup.ps1 first."
}

if (-not (Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process `
        -FilePath $python `
        -ArgumentList "-m", "uvicorn", "applypilot.main:app", "--host", "127.0.0.1", "--port", "8765" `
        -WorkingDirectory $root `
        -WindowStyle Hidden
}
