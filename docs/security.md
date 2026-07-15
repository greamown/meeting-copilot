# Security

Only `reverse-proxy` publishes a port, bound to loopback by default. Frontend, backend, PostgreSQL, Redis, STT, Codex, and TTS remain on private Compose networks. Remote exposure requires an authenticated HTTPS configuration. WebSockets validate Origin and reject frames larger than 64 KB. Repository paths are resolved and allowlisted. Codex commands use argument arrays and no shell concatenation.

Internal worker requests use a randomly generated bearer token mounted through a Docker secret. The PostgreSQL password is also delivered through a Docker secret. Neither value is placed in Compose environment variables, application logs, or the database. The generated files under `runtime/secrets/` are ignored by Git and should be readable only by the local operator.

Codex authentication is owned by `cli-worker`. `CODEX_HOME` is stored in the private `codex-auth` volume and is never mounted into `backend` or `frontend`. API responses expose only authentication state and sanitized command results; they never return the Codex token or authentication files.

Secret-bearing headers, common token fields, and token-shaped strings are redacted before persistence. Provider API keys remain in environment variables or Docker secrets. Diagnostic bundles contain sanitized application state only. Audio saving requires explicit meeting consent and can be deleted independently.
