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
  "1. Run: ./scripts/start.sh" \
  "2. Load the extension folder as an unpacked Chrome/Edge extension." \
  "3. Connect Gemini, OpenAI, or Anthropic securely inside the side panel."
