#!/bin/bash
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
output_dir="${MC_TLS_OUTPUT_DIR:-$project_root/runtime/tls}"
host_ip="${1:-${MC_TLS_HOST_IP:-}}"

if [[ -z "$host_ip" ]] && command -v ip >/dev/null 2>&1; then
    host_ip=$(ip route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i <= NF; i++) if ($i == "src") {print $(i + 1); exit}}')
fi
if [[ -z "$host_ip" ]] && command -v hostname >/dev/null 2>&1; then
    host_ip=$(hostname -I 2>/dev/null | awk '{print $1}')
fi
if [[ ! "$host_ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
    echo "Unable to detect a LAN IPv4 address. Pass one explicitly:" >&2
    echo "  ./scripts/generate_cert.sh 192.168.1.20" >&2
    exit 1
fi

mkdir -p "$output_dir"
umask 077

openssl req -x509 -newkey rsa:4096 -nodes \
    -out "$output_dir/cert.pem" \
    -keyout "$output_dir/key.pem" \
    -days "${MC_TLS_CERT_DAYS:-365}" \
    -subj "/C=TW/O=Meeting Copilot/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:$host_ip" \
    >/dev/null 2>&1

chmod 0644 "$output_dir/cert.pem"
chmod 0640 "$output_dir/key.pem"

echo "TLS certificate generated in $output_dir"
echo "SAN: localhost, 127.0.0.1, $host_ip"
echo "This development certificate is self-signed and must be trusted on client devices."
