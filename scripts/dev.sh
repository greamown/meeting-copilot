#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON=.venv/bin/python
[[ -x "$PYTHON" ]] || PYTHON=python3
export PYTHONPATH="$PWD/backend:$PWD/.python-packages${PYTHONPATH:+:$PYTHONPATH}"
"$PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!
(cd frontend && npm run dev) &
FRONTEND_PID=$!
trap 'kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true' EXIT INT TERM
echo 'Meeting Copilot: http://127.0.0.1:5173'
wait -n "$BACKEND_PID" "$FRONTEND_PID"
