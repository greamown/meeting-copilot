# Configuration

All process settings use the `MC_` prefix; see `.env.example`. Provider records hold public configuration and environment-variable secret references only. The default providers are `codex-local`, `local-stt-primary`, and `browser-tts`.

Repository access requires both meeting-level opt-in and a resolved path below one of the comma-separated `MC_REPOSITORY_ROOTS`. Network and repository context are disabled by default.
