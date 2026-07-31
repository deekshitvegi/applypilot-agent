# Check that everything lines up before blaming the code.
#
#   .\scripts\doctor.ps1
#
# The check that matters most is the last one: the version the service is
# actually running against the version in the extension manifest. They drift
# whenever the service is left running across a change, and chasing a bug that
# was fixed on disk an hour ago costs an afternoon.

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Report($ok, $label, $detail) {
    $mark = if ($ok) { "  ok  " } else { " fail " }
    Write-Host "[$mark] $label"
    if ($detail) { Write-Host "         $detail" }
}

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
Report (Test-Path $venvPython) ".venv exists" $venvPython

if (Test-Path $venvPython) {
    $pyVersion = & $venvPython --version 2>&1
    Report $? "interpreter runs" $pyVersion
    & $venvPython -c "import applypilot" 2>$null
    Report ($LASTEXITCODE -eq 0) "applypilot importable"
}

$manifestPath = Join-Path $root "extension\manifest.json"
$manifestVersion = $null
if (Test-Path $manifestPath) {
    $manifestVersion = (Get-Content $manifestPath -Raw | ConvertFrom-Json).version
    Report $true "extension manifest" "version $manifestVersion"
} else {
    Report $false "extension manifest" "not found at $manifestPath"
}

$health = $null
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8765/health" -TimeoutSec 3
    Report $true "service answering" "version $($health.version), data in $($health.data_dir)"
} catch {
    Report $false "service answering" "nothing on 127.0.0.1:8765 -- run .\scripts\start.ps1"
}

if ($health -and $manifestVersion) {
    $match = $health.version -eq $manifestVersion
    Report $match "service and extension agree" `
        "service $($health.version) vs manifest $manifestVersion$(if (-not $match) { '  <-- restart the service, then reload the extension' })"
}

if ($health) {
    Report $health.onboarding_complete "profile set up" `
        $(if ($health.missing_for_applications) { "still missing: " + ($health.missing_for_applications -join ', ') } else { "nothing missing" })
    Report $health.model_configured "model key saved" `
        $(if (-not $health.model_configured) { "matching still works; wording does not" } else { "" })
}
