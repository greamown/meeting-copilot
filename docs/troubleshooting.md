# Troubleshooting

- GPU reservation fails: install NVIDIA Container Toolkit and verify `docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu24.04 nvidia-smi`.
- STT remains unhealthy: first model download can take several minutes; inspect `docker compose logs stt-worker` and the `whisper_models` volume.
- Codex is unauthenticated: run `make codex-login`, then `docker compose exec codex-worker codex login status`.
- API is waiting: `meeting-api` starts only after PostgreSQL, Redis, STT, and Codex worker healthchecks pass.
- Microphone is denied: use the localhost URL and grant browser permission.
- Reset application data: `docker compose down -v` deletes all named volumes, including Codex authentication. Use only when a complete reset is intended.
