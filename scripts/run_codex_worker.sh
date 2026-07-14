#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/backend:$PWD/.python-packages${PYTHONPATH:+:$PYTHONPATH}"
echo 'Codex jobs are executed by the host Meeting API worker; starting local-only API on port 8000.'
exec "${PYTHON:-python3}" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
