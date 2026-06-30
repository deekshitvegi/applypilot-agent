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

Write-Host "ApplyPilot setup complete." -ForegroundColor Green
Write-Host "1. Run: .\scripts\start.ps1"
Write-Host "2. Load the extension folder as an unpacked Chrome/Edge extension."
Write-Host "3. Connect Gemini, OpenAI, or Anthropic securely inside the side panel."
