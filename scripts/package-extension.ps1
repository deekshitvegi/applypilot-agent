$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$extension = Join-Path $root "extension"
$dist = Join-Path $root "dist"
$archive = Join-Path $dist "applypilot-extension.zip"

New-Item -ItemType Directory -Path $dist -Force | Out-Null
if (Test-Path -LiteralPath $archive) {
    Remove-Item -LiteralPath $archive -Force
}

Compress-Archive -Path (Join-Path $extension "*") -DestinationPath $archive
Write-Host "Created $archive" -ForegroundColor Green
