# Meeting Copilot

Local-first meeting transcription and discussion assistance. Every server component runs in Docker Compose; the browser is the only host-side runtime. Codex CLI is the sole LLM reasoning engine.

## Prerequisites

- Docker Engine with Compose v2.
- NVIDIA driver and NVIDIA Container Toolkit for the A6000.
- A browser with microphone permission.

Python, Node.js, FFmpeg, faster-whisper, Codex CLI, PostgreSQL, and Redis are installed inside images. They are not required on the host.

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
codex-worker
tts-worker
postgres
redis
```

Open <https://localhost> or `https://<host-lan-ip>` from a device on the same network. HTTP port 80 redirects to HTTPS; no backend or worker port is published.

On first start, `scripts/generate_cert.sh` generates a self-signed certificate for localhost and the detected LAN IPv4. To select the address explicitly:

```bash
./scripts/generate_cert.sh 192.168.1.20
```

Client devices must trust the generated development certificate before browser microphone APIs and WebSockets can be used without certificate warnings. The certificate and private key stay under ignored `runtime/tls`; the key is mounted read-only and is not returned by the application.

SQLite compatibility mode remains available:

```bash
make dev-sqlite
```

## Codex authentication in Docker

After `codex-worker` is running:

```bash
make codex-login
# equivalent:
docker compose exec codex-worker codex login --device-auth
```

Verify without displaying credentials:

```bash
docker compose exec codex-worker codex login status
```

Authentication is stored only in the `codex-auth` named volume. It is not mounted into backend, frontend, STT, TTS, PostgreSQL, or Redis. Do not use `docker compose down -v` unless authentication and all persistent data should be deleted.

Codex runs with `--sandbox read-only --ephemeral --output-schema`. Repository context remains disabled unless a read-only volume and allowlisted container path are explicitly added through a Compose override.

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
docker compose logs -f backend stt-worker codex-worker
docker compose exec postgres pg_isready -U meeting -d meeting_copilot
docker compose exec redis redis-cli ping
```

See [configuration](docs/configuration.md), [Codex authentication](docs/codex-auth.md), [security](docs/security.md), and [operations](docs/operations.md).

## Implemented workflows

- Project dashboards with meeting history, glossary, and versioned project memory.
- Realtime microphone streaming, faster-whisper transcription, Codex analysis, rolling state, and local TTS.
- Meeting completion summaries plus Markdown, JSON, PDF, VTT, and SRT exports.
- Immutable decision history with confirmation, rejection, superseding versions, search, and filters.
- Action tracking by owner, project, meeting, status, due date, and priority.
- Cross-source knowledge search over meetings, transcripts, decisions, risks, questions, actions, project memory, and uploaded text documents.
- Independent UI, meeting input, secondary input, transcript display, translation, suggestion, summary, export, and TTS languages for Traditional Chinese, Simplified Chinese, English, Japanese, and Korean.
- Optional Codex translation stored beside the original transcript, with project glossary spelling and do-not-translate enforcement.

The web application exposes these as `/projects`, `/decisions`, `/actions`, `/knowledge`, `/meetings`, and `/history`; every workflow uses persisted API data.
