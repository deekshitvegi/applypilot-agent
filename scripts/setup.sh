#!/usr/bin/env bash
# One-time setup on macOS or Linux. See setup.ps1 for Windows.
set -euo pipefail
cd "$(dirname "$0")/.."

python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip --quiet
./.venv/bin/python -m pip install -e ".[dev]"
./.venv/bin/python -m playwright install chromium

echo
echo "Done. Next:"
echo "  1. ./scripts/start.sh"
echo "  2. chrome://extensions -> Developer mode -> Load unpacked -> the extension folder"
