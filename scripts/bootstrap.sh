#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p runtime/secrets runtime/meetings
chmod 700 runtime/secrets
[[ -s runtime/secrets/worker-token ]] || openssl rand -hex 32 > runtime/secrets/worker-token
[[ -s runtime/secrets/postgres-password ]] || openssl rand -hex 24 > runtime/secrets/postgres-password
chmod 600 runtime/secrets/worker-token runtime/secrets/postgres-password
if [[ ! -s runtime/tls/cert.pem || ! -s runtime/tls/key.pem ]]; then
  ./scripts/generate_cert.sh
fi
export HOST_GID="${HOST_GID:-$(id -g)}"
docker compose build
echo 'Docker images and secrets are ready. Run: make dev'
