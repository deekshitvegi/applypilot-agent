# Have the local service start itself when you sign in.
#
#   .\scripts\install-autostart.ps1            turn it on
#   .\scripts\install-autostart.ps1 -Remove    turn it off again
#
# It puts one shortcut in your own Startup folder. Nothing is installed for
# other users, nothing needs administrator, and nothing is written outside your
# own profile -- so undoing it is deleting one file, which -Remove does.
#
# The shortcut runs pythonw.exe rather than python.exe: same interpreter, no
# console window, so nothing flashes up or sits in your taskbar.
#
# The service still listens on 127.0.0.1 only, exactly as it does when you
# start it by hand.

param(
    [switch]$Remove,
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$startup = [Environment]::GetFolderPath("Startup")
$link = Join-Path $startup "ApplyPilot service.lnk"

if ($Remove) {
    if (Test-Path $link) {
        Remove-Item $link
        Write-Host "Removed. It will not start on its own any more."
        Write-Host "Anything already running keeps running until you sign out."
    }
    else {
        Write-Host "It was not set to start on its own."
    }
    return
}

$pythonw = Join-Path $root ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $pythonw)) {
    throw "No .venv here yet. Run .\scripts\setup.ps1 first."
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($link)
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = "-m applypilot --port $Port"
$shortcut.WorkingDirectory = $root
$shortcut.Description = "ApplyPilot's local service, on 127.0.0.1:$Port"
$shortcut.WindowStyle = 7          # minimised; pythonw shows nothing anyway
$shortcut.Save()

Write-Host "Done. It will start by itself every time you sign in."
Write-Host "Shortcut: $link"

# Start it now too, so there is nothing to wait for.
$already = $false
try {
    $null = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/health" -UseBasicParsing -TimeoutSec 3
    $already = $true
}
catch { }

if ($already) {
    Write-Host "It is already running."
}
else {
    Start-Process -FilePath $pythonw -ArgumentList "-m", "applypilot", "--port", $Port `
        -WorkingDirectory $root -WindowStyle Hidden
    Start-Sleep -Seconds 4
    try {
        $health = (Invoke-WebRequest -Uri "http://127.0.0.1:$Port/health" -UseBasicParsing -TimeoutSec 5).Content
        Write-Host "Started: $health"
    }
    catch {
        Write-Warning "Started it, but it is not answering yet. Give it a moment and reload the panel."
    }
}
