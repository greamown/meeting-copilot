#!/usr/bin/env bash
set -u
printf 'OS: '; uname -sr
printf 'Python: '; python3 --version
printf 'Codex: '; codex --version 2>&1 || true
printf 'FFmpeg: '; ffmpeg -version 2>/dev/null | head -1 || true
printf 'Docker: '; docker --version 2>&1 || true
printf 'GPU: '; nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>&1 || true
