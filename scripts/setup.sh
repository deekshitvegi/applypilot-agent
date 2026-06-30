#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

.venv/bin/python -m pip install -e .

if [ ! -f .env ]; then
  cp .env.example .env
fi

printf '%s\n' \
  "ApplyPilot setup complete." \
  "1. Put a newly created Gemini key in .env (GEMINI_API_KEY=...)." \
  "2. Run: ./scripts/start.sh" \
  "3. Load the extension folder as an unpacked Chrome/Edge extension."
