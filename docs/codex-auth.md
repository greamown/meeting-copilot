# Codex authentication

Codex CLI and authentication live entirely inside `codex-worker`.

```bash
make dev
make codex-login
docker compose exec codex-worker codex login status
```

Device authentication persists in the `codex_home` named volume. Other containers cannot mount this volume. Setup and Diagnostics receive only sanitized status from the worker API; credential files and token values are never returned.

For a custom OpenAI-compatible Codex provider, inject its secret into `codex-worker` with a Compose secret or environment reference and configure the provider inside the persistent Codex home. Do not inject Codex credentials into `meeting-web` or `meeting-api`.
