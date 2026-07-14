# Architecture

The React client streams framed 16 kHz PCM through a meeting-scoped WebSocket. FastAPI validates frame size, origin, sequence, and meeting state, then sends four-second windows to one reusable faster-whisper model. Final transcript segments and monotonically ordered events are committed to SQLAlchemy storage before broadcast.

Manual and deterministic triggers create `codex_runs`. `CodexManager` holds a per-meeting lock, creates an isolated runtime directory, and launches the host Codex CLI with a read-only ephemeral sandbox and JSON output schema. A failed or slow run does not block audio, events, or meeting controls. Valid suggestions pass evidence checks and similarity deduplication before publication.

SQLite and the in-process event hub are the development defaults. SQLAlchemy URLs support PostgreSQL; Redis/PostgreSQL Compose profiles are provided for the production deployment boundary.
