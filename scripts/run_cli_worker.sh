#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose up -d --build codex-worker
docker compose logs --follow codex-worker
