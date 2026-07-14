#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p runtime/secrets runtime/meetings
chmod 700 runtime/secrets
if [[ ! -s runtime/secrets/worker-token ]]; then
  openssl rand -hex 32 > runtime/secrets/worker-token
fi
if [[ ! -s runtime/secrets/postgres-password ]]; then
  openssl rand -hex 24 > runtime/secrets/postgres-password
fi
chmod 600 runtime/secrets/worker-token runtime/secrets/postgres-password
if [[ ! -s runtime/tls/cert.pem || ! -s runtime/tls/key.pem ]]; then
  ./scripts/generate_cert.sh
fi
export HOST_GID="${HOST_GID:-$(id -g)}"
COMPOSE_ARGS=()
if [[ ${1:-} == "--profile" ]]; then
  COMPOSE_ARGS=(--profile "$2")
  shift 2
fi
exec docker compose "${COMPOSE_ARGS[@]}" up --build "$@"
