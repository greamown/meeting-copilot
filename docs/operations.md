# Operations

Use `make dev` for host Codex authentication, `docker compose up --build` for isolated SQLite operation, and the `production` profile for PostgreSQL/Redis dependencies. On startup, active/paused meetings become interrupted and unfinished Codex jobs become failed.

Health: `/api/health`; readiness context: `/api/system/status`; diagnostics: `/api/diagnostics`; sanitized bundle: `/api/diagnostics/bundle`.
