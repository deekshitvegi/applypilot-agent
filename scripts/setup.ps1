$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root

if (-not (Test-Path -LiteralPath ".venv")) {
    python -m venv .venv
}

& ".venv\Scripts\python.exe" -m pip install -e "."

if (-not (Test-Path -LiteralPath ".env")) {
    Copy-Item -LiteralPath ".env.example" -Destination ".env"
}

& ".\scripts\enable-autostart.ps1"

Write-Host "ApplyPilot setup complete." -ForegroundColor Green
Write-Host "1. Load the extension folder as an unpacked Chrome/Edge extension."
Write-Host "2. Open a job page and click ApplyPilot. The companion starts automatically."
Write-Host "3. Select local Ollama, or connect Gemini, OpenAI, or Anthropic inside Settings."
