# Meeting Copilot

Local-first meeting transcription and discussion assistance. Every server component runs in Docker Compose; the browser is the only host-side runtime. Codex CLI and Claude Code are the supported LLM reasoning engines, selectable per meeting.

## Prerequisites

- Docker Engine with Compose v2.
- NVIDIA driver and NVIDIA Container Toolkit for the A6000.
- A browser with microphone permission.

Python, Node.js, FFmpeg, faster-whisper, Codex CLI, Claude Code, PostgreSQL, and Redis are installed inside images. They are not required on the host.

## One-command startup

```bash
make dev
```

This generates local worker/PostgreSQL secrets under ignored `runtime/secrets`, builds images, and starts:

```text
reverse-proxy
frontend
backend
stt-worker
cli-worker
tts-worker
postgres
redis
```

Open <https://localhost:8443> or `https://<host-lan-ip>:8443` from a device on the same network. HTTP port 80 redirects to `:8443`; no backend or worker port is published.

On first start, `scripts/generate_cert.sh` generates a self-signed certificate for localhost and the detected LAN IPv4. To select the address explicitly:

```bash
./scripts/generate_cert.sh 192.168.1.20
```

Client devices must trust the generated development certificate before browser microphone APIs and WebSockets can be used without certificate warnings. The certificate and private key stay under ignored `runtime/tls`; the key is mounted read-only and is not returned by the application.

SQLite compatibility mode remains available:

```bash
make dev-sqlite
```

## Engine authentication in Docker

Both reasoning engines authenticate inside `cli-worker`. The in-app **CLI 登入** page (`/cli-auth`) drives either flow; for Claude it shows the OAuth URL and accepts the pasted code. Equivalent CLI, after `cli-worker` is running:

```bash
# Codex (device flow)
make codex-login
docker compose exec cli-worker codex login --device-auth

# Claude Code (OAuth; paste the code from the callback page back when prompted)
make claude-login
docker compose exec -it cli-worker claude auth login --claudeai
```

Verify without displaying credentials:

```bash
docker compose exec cli-worker codex login status
docker compose exec cli-worker claude auth status
```

Codex credentials live only in the `codex-auth` volume and Claude credentials only in `claude-auth`. Neither is mounted into backend, frontend, STT, TTS, PostgreSQL, or Redis. Do not use `docker compose down -v` unless authentication and all persistent data should be deleted.

Codex runs with `--sandbox read-only --ephemeral --output-schema`; Claude runs headless with `--json-schema` and denies edits by default. Repository context remains disabled unless a read-only volume and allowlisted container path are explicitly added through a Compose override.

## STT and TTS

The `stt-worker` reserves one NVIDIA GPU and loads faster-whisper once:

```dotenv
MC_STT_MODEL=large-v3-turbo
MC_STT_DEVICE=cuda
MC_STT_COMPUTE_TYPE=float16
MC_STT_FALLBACK_MODEL=medium
```

Models persist in the `model-cache` volume. Run the in-container benchmark with `make benchmark-stt`.

Browser SpeechSynthesis remains available. The authenticated `tts-worker` supplies local `espeak-ng` synthesis and starts with the standard Compose stack.

## Database, tests, and operations

PostgreSQL and Redis start by default. PostgreSQL credentials and the internal worker token are generated files, mounted as Docker secrets, and never returned by APIs.

```bash
make migrate
make test
make lint
make smoke-test
make down
```

Useful diagnostics:

```bash
docker compose ps
docker compose logs -f backend stt-worker cli-worker
docker compose exec postgres pg_isready -U meeting -d meeting_copilot
docker compose exec redis redis-cli ping
```

See [configuration](docs/configuration.md), [engine authentication](docs/engine-auth.md), [security](docs/security.md), and [operations](docs/operations.md).

## Implemented workflows

- Project dashboards with meeting history, glossary, and versioned project memory.
- Realtime microphone streaming, faster-whisper transcription, Codex or Claude Code analysis, rolling state, and local TTS.
- Meeting completion summaries plus Markdown, JSON, PDF, VTT, and SRT exports.
- Immutable decision history with confirmation, rejection, superseding versions, search, and filters.
- Action tracking by owner, project, meeting, status, due date, and priority.
- Cross-source knowledge search over meetings, transcripts, decisions, risks, questions, actions, project memory, and uploaded text documents.
- Independent UI, meeting input, secondary input, transcript display, translation, suggestion, summary, export, and TTS languages for Traditional Chinese, Simplified Chinese, English, Japanese, and Korean.
- Optional Codex translation stored beside the original transcript, with project glossary spelling and do-not-translate enforcement.

The web application exposes these as `/projects`, `/decisions`, `/actions`, `/knowledge`, `/meetings`, and `/history`; every workflow uses persisted API data.
