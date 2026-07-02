$ErrorActionPreference = "Stop"

$shortcutPath = Join-Path ([Environment]::GetFolderPath("Startup")) "ApplyPilot.lnk"
if (Test-Path -LiteralPath $shortcutPath) {
    Remove-Item -LiteralPath $shortcutPath -Force
}
Write-Host "ApplyPilot automatic startup is disabled." -ForegroundColor Yellow

