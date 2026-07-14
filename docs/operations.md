# Operations

`make dev` is the default PostgreSQL/Redis/GPU stack. `make dev-sqlite` overrides only the meeting database URL while preserving the same containerized service boundary. `make dev-tts` activates the optional TTS profile.

Persistent volumes:

- `postgres_data`: meetings, transcripts, events, suggestions, decisions, tasks, project memory, and knowledge documents.
- `redis_data`: Redis persistence.
- `whisper_models`: faster-whisper/Hugging Face model cache.
- `codex_home`: Codex authentication and user configuration.
- `codex_runtime`: isolated Codex meeting runtime files, never credentials.

The bind-mounted `runtime` directory contains saved audio and sanitized application runtime data. `runtime/secrets` is ignored by Git and mounted read-only as Docker secrets.

Health endpoints are `/api/health`, STT `:8001/health`, Codex `:8002/health`, and optional TTS `:8003/health` inside the Compose network. Use `docker compose ps` and `docker compose logs` from the host.
