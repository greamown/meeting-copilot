# Meeting Copilot

Local-first meeting transcription and discussion assistance. Browser audio is converted to 16 kHz mono PCM, transcribed with `faster-whisper`, and persisted locally. **Codex CLI is the only LLM reasoning engine.** Suggestions are schema-validated and never spoken without a user action by default.

## Quick start (SQLite)

Prerequisites: Python 3.10+ (`python3-venv` recommended), Node 22+, FFmpeg, and Codex CLI. An NVIDIA driver is required for CUDA STT.

```bash
make setup
make migrate
make dev
```

Open <http://127.0.0.1:5173>. Both API and web UI bind to localhost. `make setup` falls back to a workspace-local `.python-packages` directory if `venv` is unavailable.

Docker-only development is one command and uses SQLite:

```bash
docker compose up --build
```

Open <http://127.0.0.1:8080>. For authenticated Codex jobs, use `make dev` on the host; credentials are user-scoped and are not mounted into containers.

## Codex authentication

```bash
codex login --device-auth
codex login status
make codex-worker
```

Alternatively use Setup > Codex validation > **Start device login**. Custom providers must reference an environment variable name such as `OPENAI_API_KEY`; the application stores only that name. It never reads or serves `~/.codex/auth.json`.

Codex execution uses `codex exec --sandbox read-only --ephemeral --output-schema ...`. Repository context is off by default and paths must be within `MC_REPOSITORY_ROOTS`.

## STT and TTS

Default STT: `large-v3-turbo`, CUDA, float16, VAD, Chinese with English terms. Configure in `.env` or Providers:

```dotenv
MC_STT_MODEL=large-v3-turbo
MC_STT_DEVICE=cuda
MC_STT_COMPUTE_TYPE=float16
MC_STT_FALLBACK_MODEL=medium
```

Run `make benchmark-stt` to test model loading, or `PYTHONPATH=backend:.python-packages python3 scripts/benchmark_stt.py fixture.wav` for real-time factor and a five-minute stability loop. Results are written to `runtime/stt-benchmark.json`.

Browser SpeechSynthesis is the default TTS adapter. Select voice, rate, and volume under Settings, then use **Speak** on a non-ignored suggestion. HTTP TTS endpoints can be registered under Providers; automatic speech is disabled.

## Database and tests

```bash
make migrate
make test
make lint
make smoke-test
```

SQLite data is stored in `runtime/meeting-copilot.db`. Production profiles are available with `docker compose --profile production up`; set `MC_DATABASE_URL` and `MC_REDIS_URL` explicitly.

## Troubleshooting

- `ensurepip is not available`: install `python3-venv`, or rerun `make setup` to use `.python-packages`.
- `nvidia-smi` fails: install the NVIDIA driver and container toolkit; STT explicitly falls back to `medium` CPU int8.
- Codex shows unauthenticated: run `codex login status`, then `codex login --device-auth` as the same OS user running the backend.
- Microphone denied: use localhost/HTTPS, allow browser permission, and rerun Setup > Microphone.
- No transcript: verify FFmpeg, STT model access, GPU memory, and Diagnostics events.
- A stale active meeting becomes `interrupted` at backend restart and can be resumed.

See [configuration](docs/configuration.md), [security](docs/security.md), and [operations](docs/operations.md).
