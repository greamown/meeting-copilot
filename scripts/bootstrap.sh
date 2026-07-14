#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
cp -n .env.example .env 2>/dev/null || true
if python3 -m venv .venv 2>/dev/null; then
  .venv/bin/pip install -e 'backend[dev,stt]'
else
  echo 'python3-venv unavailable; installing into workspace .python-packages'
  (cd backend && python3 -m pip install --target ../.python-packages '.[dev,stt]')
fi
(cd frontend && npm install)
mkdir -p runtime/meetings
echo 'Setup complete. Run: make dev'
