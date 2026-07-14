# Security

Services bind to loopback by default. Remote exposure requires an authenticated reverse proxy and HTTPS. WebSockets validate Origin and reject frames larger than 64 KB. Repository paths are resolved and allowlisted. Codex commands use argument arrays and no shell concatenation.

Secret-bearing headers, common token fields, and token-shaped strings are redacted before persistence. Provider API keys remain in environment variables. Diagnostic bundles contain sanitized application state only. Audio saving requires explicit meeting consent and can be deleted independently.
