# Codex authentication

Authentication belongs to the OS user running the backend. Use `codex login --device-auth`, the Setup wizard device flow, or an environment-backed custom provider. Never mount or copy credential JSON into this repository.

Status calls use `codex login status`. Sanitized status and errors are visible in Setup and Diagnostics; tokens and raw credential files are never exposed.
