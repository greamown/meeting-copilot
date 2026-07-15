# Engine authentication

Both reasoning engines — Codex CLI and Claude Code — and their credentials live entirely inside `cli-worker`. The backend never sees credential contents; it only relays sanitized status from the worker API. Pick the engine per meeting in Meeting prep; sign in from the in-app **CLI 登入** page (`/cli-auth`) or the CLI below.

## Codex (device flow)

```bash
make dev
make codex-login
# equivalent:
docker compose exec cli-worker codex login --device-auth
docker compose exec cli-worker codex login status
```

Device authentication persists in the `codex-auth` named volume.

## Claude Code (OAuth)

Claude uses an OAuth flow: it prints a sign-in URL, and after you authorize, the callback page shows a code you paste back. The **CLI 登入** page surfaces the URL and provides the paste field; the equivalent CLI is:

```bash
make claude-login
# equivalent (interactive, to paste the code back):
docker compose exec -it cli-worker claude auth login --claudeai
docker compose exec cli-worker claude auth status
```

Claude authentication persists in the `claude-auth` named volume (`CLAUDE_CONFIG_DIR=/home/codex/.claude`). If interactive login is impractical in your deployment, seed `claude-auth` with an existing `~/.claude/.credentials.json`, or set `ANTHROPIC_API_KEY` on `cli-worker` for Console billing.

## Isolation

Neither `codex-auth` nor `claude-auth` is mounted into `backend`, `frontend`, STT, TTS, PostgreSQL, or Redis. Setup and Diagnostics receive only sanitized status from the worker API; credential files and token values are never returned. `docker compose down -v` deletes both volumes — do not run it unless authentication should be reset.

For a custom OpenAI-compatible Codex provider, inject its secret into `cli-worker` with a Compose secret or environment reference and configure the provider inside the persistent Codex home. Do not inject engine credentials into `frontend` or `backend`.
