#!/usr/bin/env bash
set -euo pipefail
POSTGRES_PASSWORD_FILE=${MC_POSTGRES_PASSWORD_FILE:-/run/secrets/postgres_password}
if [[ -z ${MC_DATABASE_URL:-} && -f $POSTGRES_PASSWORD_FILE ]]; then
  POSTGRES_PASSWORD=$(cat "$POSTGRES_PASSWORD_FILE")
  export MC_DATABASE_URL="postgresql+asyncpg://meeting:${POSTGRES_PASSWORD}@postgres:5432/meeting_copilot"
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
