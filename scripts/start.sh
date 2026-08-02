#!/usr/bin/env bash
# Start the local service. Listens on 127.0.0.1 only.
#
# Restart this after any Python change: a running service keeps serving the code
# it started with.
set -euo pipefail
cd "$(dirname "$0")/.."
exec ./.venv/bin/python -m applypilot "$@"
