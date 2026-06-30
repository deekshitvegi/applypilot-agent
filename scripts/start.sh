#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

if [ ! -x .venv/bin/python ]; then
  printf '%s\n' "ApplyPilot is not set up. Run ./scripts/setup.sh first." >&2
  exit 1
fi

exec .venv/bin/python -m uvicorn applypilot.main:app --host 127.0.0.1 --port 8765
