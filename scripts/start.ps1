# Start the local service.
#
#   .\scripts\start.ps1            run it in this window
#   .\scripts\start.ps1 -Reload    restart it whenever a Python file changes
#
# The service listens on 127.0.0.1 only. Stop it with Ctrl+C.
#
# Restart this after any Python change. A running service keeps serving the code
# it started with, and the panel will tell you when its version and the
# extension's have drifted apart.

param(
    [switch]$Reload,
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    throw "No .venv here yet. Run .\scripts\setup.ps1 first."
}

$args = @("-m", "applypilot", "--port", $Port)
if ($Reload) { $args += "--reload" }

& $venvPython @args
