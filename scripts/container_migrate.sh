#!/usr/bin/env bash
set -euo pipefail
POSTGRES_PASSWORD_FILE=${MC_POSTGRES_PASSWORD_FILE:-/run/secrets/postgres_password}
POSTGRES_PASSWORD=$(cat "$POSTGRES_PASSWORD_FILE")
export MC_DATABASE_URL="postgresql+asyncpg://meeting:${POSTGRES_PASSWORD}@postgres:5432/meeting_copilot"
cd /app/backend
exec alembic upgrade head
