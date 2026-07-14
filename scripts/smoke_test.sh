#!/usr/bin/env bash
set -euo pipefail
BASE_URL=${BASE_URL:-http://127.0.0.1:8000}
curl -fsS "$BASE_URL/api/health"
curl -fsS "$BASE_URL/api/system/status" > runtime/system-status.json
curl -fsS -X POST "$BASE_URL/api/diagnostics/migrations"
if rg -i 'bearer [a-z0-9_-]{8,}|sk-[a-z0-9]' runtime --glob '*.json'; then
  echo 'Potential secret found in runtime output' >&2; exit 1
fi
echo 'Smoke test passed'
