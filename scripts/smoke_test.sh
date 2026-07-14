#!/usr/bin/env bash
set -euo pipefail
BASE_URL=${BASE_URL:-https://127.0.0.1}
CURL_TLS_ARGS=()
if [[ ${MC_TLS_VERIFY:-false} != true ]]; then
  CURL_TLS_ARGS=(-k)
fi
curl "${CURL_TLS_ARGS[@]}" -fsS "$BASE_URL/api/health"
curl "${CURL_TLS_ARGS[@]}" -fsS "$BASE_URL/api/system/status" > runtime/system-status.json
curl "${CURL_TLS_ARGS[@]}" -fsS -X POST "$BASE_URL/api/diagnostics/migrations"
if rg -i 'bearer [a-z0-9_-]{8,}|sk-[a-z0-9]' runtime --glob '*.json'; then
  echo 'Potential secret found in runtime output' >&2; exit 1
fi
echo 'Smoke test passed'
