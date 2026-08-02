# Zip the extension folder for loading on another machine.
#
#   .\scripts\package-extension.ps1
#
# Refuses to run when the manifest version and the service version disagree,
# because shipping a mismatched pair is how you end up debugging code that is
# not the code running.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$manifest = Get-Content "extension\manifest.json" -Raw | ConvertFrom-Json
$initPath = "src\applypilot\__init__.py"
$initVersion = (Select-String -Path $initPath -Pattern '__version__ = "([^"]+)"').Matches[0].Groups[1].Value

if ($manifest.version -ne $initVersion) {
    throw "extension/manifest.json says $($manifest.version) but $initPath says $initVersion. Bump them together."
}

$out = Join-Path $root "extension.zip"
if (Test-Path $out) { Remove-Item $out }
Compress-Archive -Path "extension\*" -DestinationPath $out
Write-Host "Wrote $out (version $($manifest.version))"
