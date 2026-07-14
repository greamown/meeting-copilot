# Architecture

The deployment is fully containerized:

```text
Browser -> reverse-proxy (HTTPS) -> meeting-web -> meeting-api -> PostgreSQL / Redis
                                  |-> stt-worker (A6000)
                                  |-> codex-worker (Codex CLI)
                                  `-> optional-tts-worker
```

The React client streams framed 16 kHz PCM over a meeting WebSocket. `meeting-api` validates origin, frame size, sequence, consent, and session state, then calls the authenticated STT worker. The STT container owns the reusable faster-whisper model and its NVIDIA GPU allocation.

Deterministic triggers create persisted Codex jobs. `meeting-api` serializes jobs per meeting and calls the authenticated Codex worker. The worker alone has access to `CODEX_HOME`, creates isolated runtime directories, invokes Codex with a read-only ephemeral sandbox, repairs invalid JSON once, and validates the response schema and evidence IDs.

Project context is bounded before each Codex call and contains active project memory, glossary entries, recent knowledge documents, recent transcript segments, and recent suggestions. Uploaded knowledge never bypasses the Codex JSON/evidence validation boundary.

Language policy is captured per meeting rather than inferred from the UI locale. A secondary input language enables Whisper automatic detection for mixed-language speech. Codex requests carry separate suggestion, summary, translation, and analysis-mode targets. Generated translations are evidence-ID validated and stored in `translated_text`; they never overwrite `TranscriptSegment.text`. Glossary aliases are normalized once after STT and do-not-translate rules are re-applied to translations.

Long-term records are normalized in PostgreSQL. Decision content changes append a superseding version; task records link meetings and decisions; the knowledge search API queries documents, meetings, transcripts, decisions, risks, questions, actions, and project memory. SQLite uses the same SQLAlchemy models and API for one-command development.

Worker traffic stays on private Compose networks and requires a constant-time checked Docker secret. Only reverse-proxy ports 80 and 443 are published; the API, workers, databases, and frontend container ports are internal.
