# Codex Implementation Specification: Meeting Discussion Copilot

## 0. Mission

Build a production-oriented, self-hosted **Meeting Discussion Copilot** for a workstation equipped with an NVIDIA A6000-class GPU.

The system MUST:

1. Capture microphone audio from a browser.
2. Convert speech to text locally.
3. Maintain a live meeting transcript and structured meeting state.
4. Use **Codex CLI as the only LLM reasoning engine**.
5. Decide when an AI suggestion adds value instead of interrupting continuously.
6. Display suggestions in the meeting UI.
7. Optionally convert an approved suggestion to speech.
8. Provide web-based configuration for:
   - Codex authentication and status.
   - Codex model/provider/profile settings.
   - STT, TTS, embedding, and optional reranker API endpoints.
   - Local model settings and health checks.
9. Store meetings, transcript segments, decisions, suggestions, configuration metadata, and execution logs.
10. Run through Docker Compose where practical, while allowing the Codex worker to run on the host when authentication or sandboxing requires it.

The project MUST be implemented end to end. Do not stop after generating scaffolding or design documents.

---

## 1. Product Constraints

### 1.1 Required reasoning engine

- Codex CLI MUST be the only LLM reasoning engine.
- Do not add a dependency on another chat LLM API.
- Codex MUST be invoked through a controlled worker, not directly from the browser.
- The worker MUST support non-interactive execution.
- Codex output MUST be validated against a strict JSON Schema.
- A single meeting MUST NOT have two concurrent Codex turns.
- A failed Codex call MUST NOT stop transcription or the meeting UI.
- The application MUST provide a manual **Ask Codex** action.
- Automatic Codex invocation MUST be configurable and rate-limited.

### 1.2 Local-first operation

- STT SHOULD run locally on the A6000 device.
- TTS SHOULD run locally or through browser speech synthesis.
- Core meeting data MUST remain local by default.
- Network access by Codex MUST be disabled by default for meeting analysis.
- Repository access MUST be disabled by default and explicitly enabled per meeting.
- The system MUST clearly show when external services are configured.

### 1.3 Interaction policy

The default product behavior MUST be:

```text
Listen continuously
→ transcribe continuously
→ analyze periodically or when triggered
→ show a suggestion in the sidebar
→ require a human click before speaking
```

Automatic spoken interruption MUST be disabled by default.

---

## 2. Recommended Technology Stack

Use this stack unless a concrete implementation constraint requires another choice.

### Frontend

- React
- TypeScript
- Vite or Next.js
- Web Audio API
- AudioWorklet where supported
- WebSocket for audio and live events
- TanStack Query for API state
- Zod for client-side validation

### Backend

- Python 3.12
- FastAPI
- Pydantic v2
- SQLAlchemy 2
- Alembic
- asyncio
- WebSocket endpoints

### Database and event infrastructure

PoC mode:

- SQLite
- In-process `asyncio.Queue`

Production mode:

- PostgreSQL
- Redis Streams

The repository MUST support SQLite for one-command local startup. PostgreSQL and Redis support SHOULD be implemented through configuration.

### Local STT

Primary:

- `faster-whisper`
- Default model: `large-v3-turbo`
- CUDA when available
- VAD enabled

Fallback:

- `medium` or `small`
- CPU int8 mode

### TTS

Phase-one default:

- Browser `SpeechSynthesis`

Optional server engine:

- Pluggable OpenAI-compatible TTS endpoint or a local TTS adapter.
- The architecture MUST NOT hard-code one TTS vendor.

### Codex

- Codex CLI installed on the host or in a controlled worker environment.
- Provider and profile configuration MUST be managed at user scope, not committed to the repository.
- The application MUST never display raw Codex credential files.

---

## 3. High-Level Architecture

```text
┌────────────────────────────────────────────────────────────┐
│                        Web Client                          │
│                                                            │
│  Setup                                                     │
│  - Codex authentication                                    │
│  - Model providers                                         │
│  - Audio devices                                           │
│                                                            │
│  Meeting                                                   │
│  - Microphone stream                                       │
│  - Live transcript                                         │
│  - AI suggestions                                          │
│  - Decisions / questions / action items                     │
│                                                            │
│  History                                                   │
│  - Meeting records                                         │
│  - Search / export                                         │
└──────────────────────────────┬─────────────────────────────┘
                               │ HTTPS / WebSocket
                               ▼
┌────────────────────────────────────────────────────────────┐
│                      Meeting API                           │
│                                                            │
│  Authentication and authorization                          │
│  Session manager                                           │
│  Configuration service                                     │
│  WebSocket manager                                         │
│  Event router                                               │
│  Health aggregation                                         │
└──────────────┬────────────────┬────────────────┬────────────┘
               │                │                │
               ▼                ▼                ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ STT Worker       │  │ Meeting Engine   │  │ Codex Worker     │
│                  │  │                  │  │                  │
│ Audio buffer     │  │ Transcript state │  │ Queue            │
│ VAD              │  │ Trigger rules    │  │ CLI execution    │
│ faster-whisper   │  │ Deduplication    │  │ JSON validation  │
│ partial/final    │  │ State patches    │  │ Timeout/cancel   │
└──────────────────┘  └──────────────────┘  └──────────────────┘
               │                │                │
               └────────────────┼────────────────┘
                                ▼
                   ┌────────────────────────┐
                   │ Persistence / Events   │
                   │ SQLite/PostgreSQL      │
                   │ Redis optional         │
                   │ Audio optional         │
                   └────────────────────────┘
                                │
                                ▼
                   ┌────────────────────────┐
                   │ TTS Adapter            │
                   │ Browser default        │
                   │ Server endpoint option │
                   └────────────────────────┘
```

---

## 4. Required Web Pages

## 4.1 Initial Setup Wizard

Create a setup wizard shown when required configuration is incomplete.

Steps:

1. System check.
2. Codex authentication.
3. Codex provider/profile configuration.
4. STT configuration and benchmark.
5. TTS configuration and test playback.
6. Microphone permission and test recording.
7. Save and open the meeting dashboard.

The wizard MUST show pass/fail status for every required dependency.

System checks MUST include:

- Operating system.
- Python version.
- Docker availability.
- Codex CLI availability and version.
- FFmpeg availability.
- NVIDIA driver availability.
- CUDA availability.
- GPU model.
- GPU memory.
- Available disk space.
- Database connectivity.
- Redis connectivity when enabled.

The wizard MUST allow re-running checks.

---

## 4.2 Codex Authentication Page

The page MUST provide:

### Status

- Codex installed/not installed.
- Codex CLI version.
- Authentication status.
- Active profile.
- Active model.
- Active provider.
- Last successful test time.
- Sanitized error output.

### Supported authentication flows

Implement adapters for:

1. Existing Codex login on the host.
2. Interactive login launched by the backend with a safe user-visible flow.
3. API-key-based custom provider through an environment-variable-backed secret.
4. A custom OpenAI-compatible endpoint.

Do not parse or display access tokens from Codex credential files.

Required actions:

- `Check status`
- `Start login`
- `Cancel login`
- `Logout`
- `Test Codex`
- `Refresh`
- `View sanitized configuration`

The UI MUST warn that authentication and provider configuration are machine-level settings.

### Secret handling

- API keys MUST never be stored in plaintext in the application database.
- Use environment variables, Docker secrets, OS keyring, or an encrypted local secret file.
- API responses MUST mask secrets.
- Logs MUST redact:
  - Authorization headers.
  - API keys.
  - OAuth tokens.
  - Cookies.
  - Raw credential file content.

---

## 4.3 Model and Endpoint Settings Page

Create a model registry instead of scattered settings.

Each model configuration MUST contain:

```json
{
  "id": "local-stt-primary",
  "name": "Local Whisper",
  "role": "stt",
  "provider_type": "local_faster_whisper",
  "base_url": null,
  "api_key_secret_ref": null,
  "model": "large-v3-turbo",
  "enabled": true,
  "timeout_seconds": 60,
  "max_retries": 2,
  "extra": {
    "device": "cuda",
    "compute_type": "float16",
    "language": "zh",
    "vad_filter": true
  }
}
```

Supported roles:

- `reasoning`
- `stt`
- `tts`
- `embedding`
- `reranker`

Supported provider types:

- `codex_cli`
- `local_faster_whisper`
- `openai_compatible_stt`
- `browser_speech_synthesis`
- `openai_compatible_tts`
- `openai_compatible_embedding`
- `custom_http`

Each configuration card MUST provide:

- Name.
- Role.
- Provider type.
- Base URL.
- Model name.
- Secret reference.
- Timeout.
- Retry count.
- Enabled state.
- Advanced JSON settings.
- Health status.
- Last latency.
- `Test connection` button.
- `Set as default` button.

Reasoning provider settings MUST additionally provide:

- Codex profile.
- Codex model.
- Working directory policy.
- Sandbox policy.
- Approval policy.
- Network policy.
- Maximum execution time.
- Maximum queued jobs.
- Automatic analysis interval.
- Suggestion cooldown.

Do not let the browser directly write arbitrary Codex TOML. The backend MUST generate validated configuration from an allowlisted schema.

---

## 4.4 Main Dashboard

The dashboard MUST contain:

- `Start new meeting`
- Recent meetings
- System health
- Codex status
- STT status
- TTS status
- GPU utilization
- GPU memory utilization
- Active worker count
- Queue depth
- Storage usage
- Recent errors

Provide navigation to:

- Setup
- Providers
- Meetings
- History
- Diagnostics
- Settings

---

## 4.5 Meeting Preparation Page

Before starting a meeting, allow the user to set:

- Meeting title.
- Meeting goal.
- Language.
- Input microphone.
- STT provider.
- TTS provider.
- Codex profile.
- Automatic analysis enabled/disabled.
- Analysis interval.
- Suggestion cooldown.
- Human approval before speech.
- Save audio enabled/disabled.
- Repository context enabled/disabled.
- Repository path when enabled.
- Read-only repository mode.
- Reference files or notes.
- Participant names, optional.
- Privacy notice acknowledgement.

The user MUST be able to run a microphone test before starting.

---

## 4.6 Live Meeting Page

The live page MUST include:

### Header

- Meeting title.
- Elapsed time.
- Recording state.
- STT status.
- Codex status.
- Queue state.
- Start/pause/resume/end controls.

### Transcript panel

- Partial transcript.
- Final transcript.
- Timestamp.
- Speaker label when available.
- Edit transcript action.
- Pin important segment.
- Search.
- Auto-scroll toggle.

### AI suggestion panel

Each suggestion MUST show:

- Category.
- Suggestion.
- Reason.
- Confidence.
- Trigger.
- Creation time.
- Related transcript segment.
- Status.

Actions:

- Accept.
- Ignore.
- Copy.
- Edit.
- Speak.
- Add as decision.
- Add as open question.
- Add as action item.

### Meeting-state panel

Show:

- Current topic.
- Confirmed decisions.
- Open questions.
- Risks.
- Action items.
- Parking lot.
- Last Codex analysis time.

### Manual Codex input

Provide an **Ask Codex** input with:

- Text question.
- Optional transcript time range.
- Optional repository context.
- Submit.
- Cancel.
- Progress.
- Result.

### Codex job visibility

Show these states:

```text
queued
preparing_context
running
validating
completed
failed
timed_out
cancelled
```

The live meeting MUST remain usable when Codex is slow or unavailable.

---

## 4.7 Meeting History and Detail Page

Required capabilities:

- List meetings.
- Filter by date, title, participant, status.
- Open meeting details.
- View transcript.
- View suggestions.
- View accepted/ignored ratio.
- View decisions.
- View questions.
- View action items.
- View Codex runs and sanitized errors.
- Export Markdown.
- Export JSON.
- Export WebVTT or SRT.
- Delete meeting.
- Delete saved audio independently.
- Re-run Codex analysis on a selected transcript range.

---

## 4.8 Diagnostics Page

Show:

- Backend health.
- Database health.
- Redis health.
- Codex CLI version/status.
- Provider health.
- STT model load state.
- GPU stats.
- FFmpeg status.
- WebSocket status.
- Queue depth.
- Average STT latency.
- Average Codex latency.
- Last 100 sanitized events.
- Downloadable sanitized diagnostic bundle.

Provide test actions:

- Record five seconds and transcribe.
- Send a fixed Codex JSON task.
- Generate or play test speech.
- Test each configured endpoint.
- Validate database migrations.

---

## 5. Audio Pipeline

### 5.1 Browser capture

Use:

```text
16 kHz
mono
PCM signed 16-bit or Opus with deterministic server conversion
audio chunks of approximately 500–1000 ms
```

Implement:

- Microphone device selection.
- Permission handling.
- Reconnection.
- Backpressure.
- Sequence numbers.
- Client timestamp.
- Server timestamp.
- Lost-chunk detection.
- Audio level meter.
- Mute detection.

### 5.2 STT worker

The worker MUST:

- Load the selected model once and reuse it.
- Expose readiness and liveness endpoints.
- Accept streamed or chunked audio.
- Apply VAD.
- Generate partial and final transcript events.
- Avoid duplicate overlap text.
- Preserve timestamps.
- Support Chinese with English technical terms.
- Allow model/device/compute-type configuration.
- Return confidence metadata when available.
- Recover after CUDA out-of-memory errors.
- Fall back to a smaller model when explicitly configured.

Default configuration:

```yaml
engine: faster-whisper
model: large-v3-turbo
device: cuda
compute_type: float16
language: zh
vad_filter: true
beam_size: 5
```

Implement an initial benchmark command that measures:

- Model load time.
- Real-time factor.
- Peak GPU memory.
- Five-minute stability test.

Do not assume the default is optimal. Save the benchmark result and permit switching to `medium` or another configured model.

### 5.3 Speaker handling

Speaker diarization is optional for the first milestone.

The schema MUST support `speaker_id`.

Phase-one MAY provide:

- Manual speaker assignment.
- Rename speaker.
- Merge speaker labels.

Do not block MVP completion on automatic diarization.

---

## 6. Meeting State Engine

The engine MUST maintain:

```json
{
  "meeting_id": "meeting-uuid",
  "goal": "string",
  "current_topic": "string",
  "decisions": [],
  "open_questions": [],
  "risks": [],
  "action_items": [],
  "parking_lot": [],
  "recent_transcript_segment_ids": [],
  "last_codex_run_at": null,
  "last_suggestion_at": null,
  "new_transcript_characters": 0,
  "version": 1
}
```

Rules:

- Complete transcript MUST be stored separately.
- Recent context MUST be bounded by time and character count.
- State updates from Codex MUST use a patch structure.
- A state patch MUST be validated before application.
- Duplicate decisions/questions/actions MUST be rejected or merged.
- Every state mutation MUST be traceable to an event or user action.
- User edits MUST take precedence over generated state.

---

## 7. Trigger Engine

The trigger engine MUST use deterministic rules before invoking Codex.

Required triggers:

- Manual ask.
- Direct mention of the assistant.
- Explicit question.
- Periodic analysis.
- Decision keywords.
- Long discussion with no decision.
- Repeated topic.
- Silence after a question, when reliable.
- Meeting-end final analysis.

Required suppressors:

- Insufficient new transcript.
- Codex already running.
- Suggestion cooldown.
- Similar recent suggestion.
- Meeting paused.
- STT confidence below threshold.
- User disabled automatic analysis.

Default values:

```yaml
periodic_analysis_seconds: 120
minimum_new_characters: 300
codex_cooldown_seconds: 60
suggestion_cooldown_seconds: 180
maximum_recent_transcript_minutes: 10
maximum_recent_transcript_characters: 12000
automatic_analysis_enabled: true
```

These values MUST be editable from the settings UI.

---

## 8. Codex Worker

## 8.1 Responsibilities

The Codex worker MUST:

1. Accept a structured job.
2. Serialize execution per meeting.
3. Build a bounded context bundle.
4. Run Codex CLI in a restricted mode.
5. Capture structured events and final output.
6. Enforce a timeout.
7. Support cancellation.
8. Validate JSON output.
9. Retry only safe transient failures.
10. Store sanitized run metadata.
11. Return a result without exposing secrets.

## 8.2 Execution policy

Default:

```yaml
sandbox: read-only
approval_policy: never
network_access: false
repository_access: false
timeout_seconds: 180
max_retries: 1
```

When repository context is enabled:

- Path MUST be allowlisted.
- Access MUST be read-only by default.
- Codex MUST NOT modify source files.
- Codex MUST NOT run destructive commands.
- The UI MUST show that repository context is active.
- A future code-change workflow MUST be implemented separately and require explicit approval.

## 8.3 Per-meeting runtime directory

```text
runtime/
└── meetings/
    └── <meeting_id>/
        ├── AGENTS.md
        ├── meeting-state.json
        ├── recent-transcript.json
        ├── request.json
        ├── response.json
        └── runs/
```

Do not store credentials in this directory.

## 8.4 Codex instruction file

Generate an `AGENTS.md` that states:

```text
You are a meeting discussion assistant.

MUST:
- Use only the provided meeting context and explicitly enabled files.
- Do not claim facts not supported by the transcript or referenced files.
- Do not modify files.
- Do not access the network.
- Do not execute destructive commands.
- Return valid JSON conforming to the provided schema.
- Set should_suggest=false when there is no material new value.
- Avoid repeating recent suggestions.
- Keep suggestions concise and actionable.
- Distinguish facts, inferences, risks, and questions.

SHOULD:
- Detect contradictions.
- Identify missing decisions.
- Surface operational, security, reliability, cost, and maintenance risks.
- Turn vague discussion into a concrete next question.
```

## 8.5 Input schema

```json
{
  "job_id": "uuid",
  "meeting_id": "uuid",
  "job_type": "periodic_analysis",
  "meeting": {
    "title": "string",
    "goal": "string",
    "current_topic": "string",
    "decisions": [],
    "open_questions": [],
    "risks": [],
    "action_items": []
  },
  "recent_transcript": [
    {
      "segment_id": "uuid",
      "speaker_id": "speaker-1",
      "start_ms": 0,
      "end_ms": 1000,
      "text": "string",
      "confidence": 0.9
    }
  ],
  "recent_suggestions": [],
  "manual_question": null,
  "repository_context": {
    "enabled": false,
    "path": null
  }
}
```

## 8.6 Required output schema

```json
{
  "should_suggest": true,
  "confidence": 0.88,
  "category": "missing_decision",
  "suggestion": "Define a task lease and heartbeat before deciding the retry owner.",
  "reason": "The discussion covers retry behavior but does not define how failure is detected.",
  "follow_up_question": "Must the task be idempotent?",
  "evidence_segment_ids": ["uuid"],
  "state_patch": {
    "current_topic": null,
    "add_decisions": [],
    "add_open_questions": [],
    "add_risks": [],
    "add_action_items": [],
    "add_parking_lot": []
  }
}
```

Allowed categories:

- `answer`
- `missing_decision`
- `unresolved_question`
- `contradiction`
- `risk`
- `alternative`
- `summary`
- `action_item`
- `off_topic`
- `no_material_value`

Validation rules:

- `confidence` MUST be between 0 and 1.
- `suggestion` MUST have a configurable maximum length.
- `evidence_segment_ids` MUST exist in the input.
- `state_patch` MUST contain only allowed operations.
- `should_suggest=false` MUST be accepted as a successful result.
- Invalid JSON MUST trigger one constrained repair attempt, then fail safely.

---

## 9. Suggestion Validation and Deduplication

Before publishing a suggestion:

1. Validate schema.
2. Verify referenced transcript segments.
3. Reject empty content.
4. Enforce length.
5. Compare against recent suggestions.
6. Apply cooldown.
7. Check category allowlist.
8. Store the result.
9. Emit `suggestion.created`.

Deduplication SHOULD combine:

- Normalized exact comparison.
- Token or character similarity.
- Optional local embedding similarity when an embedding provider is configured.

The MVP MUST work without embeddings.

---

## 10. TTS Architecture

The TTS subsystem MUST use an adapter interface.

Required adapters:

1. Browser SpeechSynthesis.
2. OpenAI-compatible TTS HTTP endpoint.
3. Disabled/no-speech mode.

Required actions:

- Test voice.
- Select voice.
- Configure rate.
- Configure volume.
- Cancel playback.
- Prevent simultaneous playback.
- Never speak automatically unless explicitly enabled.
- Never speak an ignored suggestion.

The server MUST NOT generate TTS audio when browser speech synthesis is selected.

---

## 11. API Surface

Implement at least:

```text
GET    /api/health
GET    /api/system/status
GET    /api/system/gpu
GET    /api/codex/status
POST   /api/codex/login/start
POST   /api/codex/login/cancel
POST   /api/codex/logout
POST   /api/codex/test

GET    /api/providers
POST   /api/providers
GET    /api/providers/{id}
PUT    /api/providers/{id}
DELETE /api/providers/{id}
POST   /api/providers/{id}/test
POST   /api/providers/{id}/set-default

POST   /api/meetings
GET    /api/meetings
GET    /api/meetings/{id}
POST   /api/meetings/{id}/start
POST   /api/meetings/{id}/pause
POST   /api/meetings/{id}/resume
POST   /api/meetings/{id}/end
DELETE /api/meetings/{id}

WS     /api/meetings/{id}/audio
WS     /api/meetings/{id}/events

POST   /api/meetings/{id}/ask
POST   /api/meetings/{id}/analyze
POST   /api/codex-runs/{id}/cancel

POST   /api/suggestions/{id}/accept
POST   /api/suggestions/{id}/ignore
POST   /api/suggestions/{id}/edit
POST   /api/suggestions/{id}/speak

POST   /api/meetings/{id}/export/markdown
POST   /api/meetings/{id}/export/json
POST   /api/meetings/{id}/export/vtt
```

Every endpoint MUST use typed request and response models.

---

## 12. Event Model

Use a consistent envelope:

```json
{
  "event_id": "uuid",
  "meeting_id": "uuid",
  "type": "transcript.final",
  "created_at": "ISO-8601",
  "source": "stt-worker",
  "sequence": 1,
  "payload": {}
}
```

Required event types:

```text
meeting.created
meeting.started
meeting.paused
meeting.resumed
meeting.ended
audio.chunk.received
audio.chunk.dropped
speech.started
speech.ended
transcript.partial
transcript.final
transcript.edited
trigger.detected
codex.requested
codex.queued
codex.started
codex.completed
codex.failed
codex.timed_out
codex.cancelled
suggestion.created
suggestion.accepted
suggestion.ignored
suggestion.edited
tts.started
tts.completed
tts.failed
state.updated
system.warning
```

Events MUST be ordered per meeting using a monotonically increasing sequence.

---

## 13. Database Schema

Implement migrations for:

### `app_settings`

- id
- key
- value_json
- is_secret_reference
- created_at
- updated_at

### `model_providers`

- id
- name
- role
- provider_type
- base_url
- secret_ref
- model
- enabled
- is_default
- timeout_seconds
- max_retries
- extra_json
- created_at
- updated_at

### `meetings`

- id
- title
- goal
- language
- status
- started_at
- ended_at
- configuration_json
- audio_saved
- repository_context_enabled
- repository_path
- created_at
- updated_at

### `participants`

- id
- meeting_id
- display_name
- speaker_label
- created_at

### `transcript_segments`

- id
- meeting_id
- sequence
- speaker_id
- start_ms
- end_ms
- text
- confidence
- is_final
- is_edited
- created_at
- updated_at

### `meeting_states`

- id
- meeting_id
- version
- current_topic
- state_json
- source
- created_at

### `codex_runs`

- id
- meeting_id
- job_type
- trigger
- status
- profile
- model
- provider
- request_json
- response_json
- sanitized_stderr
- started_at
- ended_at
- duration_ms
- retry_count
- created_at

### `suggestions`

- id
- meeting_id
- codex_run_id
- category
- content
- reason
- follow_up_question
- confidence
- trigger
- status
- evidence_segment_ids_json
- created_at
- updated_at

### `decisions`

- id
- meeting_id
- content
- source
- source_suggestion_id
- created_at
- updated_at

### `open_questions`

- id
- meeting_id
- content
- status
- source
- source_suggestion_id
- created_at
- updated_at

### `risks`

- id
- meeting_id
- content
- status
- source
- source_suggestion_id
- created_at
- updated_at

### `action_items`

- id
- meeting_id
- content
- owner
- due_at
- status
- source
- source_suggestion_id
- created_at
- updated_at

### `events`

- id
- meeting_id
- sequence
- type
- source
- payload_json
- created_at

### `audio_chunks`

- id
- meeting_id
- sequence
- path
- start_ms
- end_ms
- checksum
- status
- created_at

Add appropriate indexes and foreign keys.

---

## 14. Security Requirements

- Bind to localhost by default.
- Remote access MUST require authentication.
- Add CSRF protection where applicable.
- Validate WebSocket origin.
- Limit audio frame size.
- Limit upload size.
- Sanitize file paths.
- Prevent path traversal.
- Allowlist repository roots.
- Never shell-concatenate user input.
- Invoke Codex through an argument array.
- Redact secrets from logs.
- Do not expose `~/.codex/auth.json`.
- Do not expose raw environment variables.
- Encrypt or externalize application secrets.
- Add rate limiting to login and Codex endpoints.
- Add an audit event for configuration changes.
- Require explicit consent before saving audio.
- Permit complete meeting deletion.

---

## 15. Reliability Requirements

- Reconnect WebSockets automatically.
- Preserve meeting state during frontend reload.
- Do not lose final transcript segments.
- Use idempotency keys for audio chunks and commands.
- Apply database transactions for state updates.
- Retry transient STT/TTS endpoint failures.
- Do not automatically retry an ambiguous Codex operation more than once.
- Ensure one active Codex job per meeting.
- Recover stale Codex jobs after process restart.
- Mark partial meetings as interrupted after an unclean shutdown.
- Provide graceful shutdown for workers.
- Include liveness and readiness endpoints.

---

## 16. Observability

Required metrics:

- Active meetings.
- Audio chunks received/dropped.
- STT real-time factor.
- STT queue depth.
- STT partial/final latency.
- Codex queue depth.
- Codex execution latency.
- Codex success/failure/timeout rate.
- Suggestions generated.
- Suggestions accepted/ignored.
- Duplicate suggestions suppressed.
- TTS latency.
- GPU utilization.
- GPU memory.
- Process memory.
- Database latency.

Use structured JSON logs.

Every request/job/event MUST include correlation identifiers.

---

## 17. Repository Structure

Create:

```text
meeting-copilot/
├── README.md
├── AGENTS.md
├── LICENSE
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Makefile
├── docs/
│   ├── architecture.md
│   ├── configuration.md
│   ├── codex-auth.md
│   ├── security.md
│   ├── operations.md
│   └── troubleshooting.md
├── frontend/
│   ├── package.json
│   └── src/
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── migrations/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── workers/
│   │   └── main.py
│   └── tests/
├── runtime/
│   └── .gitkeep
├── scripts/
│   ├── bootstrap.sh
│   ├── check_system.sh
│   ├── benchmark_stt.py
│   ├── run_codex_worker.sh
│   └── smoke_test.sh
└── schemas/
    ├── codex-request.schema.json
    ├── codex-response.schema.json
    └── event.schema.json
```

---

## 18. Docker and Runtime

Provide a Docker Compose configuration for:

- frontend
- backend
- stt-worker
- postgres, optional profile
- redis, optional profile

The Codex worker SHOULD run on the host for the initial implementation because host authentication and user-scoped Codex configuration are easier to secure.

Expose a local-only Codex worker API or Unix domain socket.

The backend MUST authenticate requests to the Codex worker using a local secret or socket permissions.

Provide commands:

```bash
make setup
make dev
make test
make lint
make format
make benchmark-stt
make codex-worker
make smoke-test
make down
```

---

## 19. Testing Requirements

### Unit tests

- Trigger logic.
- Cooldown.
- Transcript overlap deduplication.
- Codex request generation.
- JSON Schema validation.
- State patch validation.
- Suggestion deduplication.
- Secret redaction.
- Repository path allowlisting.
- Provider configuration validation.

### Integration tests

- Create/start/end meeting.
- WebSocket transcript flow.
- Mock STT worker.
- Mock Codex CLI process.
- Codex timeout.
- Invalid Codex JSON.
- Codex cancellation.
- Accept/ignore suggestion.
- Export Markdown/JSON/VTT.
- Provider health test.
- Restart recovery.

### End-to-end test

Automate:

1. Complete initial setup with mock providers.
2. Start a meeting.
3. Stream a fixture audio file.
4. Receive final transcript.
5. Trigger Codex.
6. Display a suggestion.
7. Accept the suggestion.
8. End meeting.
9. Export Markdown.
10. Open history detail.

### Hardware smoke test

Provide a manual or automated smoke test for the A6000 host:

- CUDA detected.
- STT model loads.
- Five-minute audio transcribes faster than real time.
- GPU memory remains stable.
- Browser can sustain a 30-minute stream.
- Codex worker can complete a structured test.
- No secrets appear in logs.

---

## 20. Acceptance Criteria

The project is complete only when all of the following are true:

1. A new installation can be started from documented commands.
2. The setup wizard detects missing dependencies.
3. Codex authentication status is visible without exposing credentials.
4. A custom Codex model provider/profile can be configured safely.
5. STT and TTS endpoints can be configured and tested from the UI.
6. The browser can capture microphone audio.
7. Live partial and final transcript is displayed.
8. The meeting continues when Codex is unavailable.
9. Manual Ask Codex works.
10. Automatic trigger rules work.
11. Codex returns validated structured output.
12. Duplicate suggestions are suppressed.
13. Suggestions can be accepted, ignored, edited, copied, and spoken.
14. Decisions, questions, risks, and action items are persisted.
15. Meetings can be reopened from history.
16. Markdown, JSON, and VTT export work.
17. Logs redact secrets.
18. Unit, integration, and end-to-end tests pass.
19. README contains exact startup and troubleshooting instructions.
20. No placeholder buttons or non-functional UI controls remain.

---

## 21. Implementation Sequence

Implement in this order:

### Milestone 1: Repository and system health

- Create repository.
- Backend/frontend baseline.
- SQLite.
- Health page.
- GPU detection.
- Codex status adapter.
- Tests.

### Milestone 2: Configuration

- Setup wizard.
- Codex auth/status.
- Provider registry.
- Secret references.
- Endpoint health tests.

### Milestone 3: Audio and STT

- Browser microphone capture.
- Audio WebSocket.
- STT worker.
- Partial/final transcript.
- Transcript persistence.
- Benchmark.

### Milestone 4: Codex reasoning

- Trigger engine.
- Codex queue.
- Codex worker.
- Restricted runtime.
- JSON Schema.
- Timeout/cancel.
- Suggestion UI.

### Milestone 5: Meeting state

- Decisions.
- Questions.
- Risks.
- Action items.
- State patches.
- Deduplication.

### Milestone 6: TTS and exports

- Browser TTS.
- HTTP TTS adapter.
- Markdown/JSON/VTT exports.
- History.

### Milestone 7: Hardening

- Security review.
- Restart recovery.
- Diagnostics.
- E2E tests.
- Documentation.
- Docker profiles.

After each milestone:

- Run tests.
- Fix failures.
- Update README.
- Commit a coherent change if Git is available.

Do not proceed while the current milestone has failing required tests.

---

## 22. Required Final Report From Codex

When implementation is complete, return:

1. Architecture summary.
2. Files created and modified.
3. Exact startup commands.
4. Exact Codex authentication setup.
5. Exact STT and TTS configuration steps.
6. Database migration commands.
7. Test commands and results.
8. A6000 benchmark results.
9. Known limitations.
10. Security assumptions.
11. Remaining optional enhancements.

Do not claim a feature is complete unless it is implemented and tested.

---

## 23. Additional Product Enhancements

Implement these only after required acceptance criteria pass:

- Meeting templates.
- Participant-specific speaker labels.
- Hotword such as “Codex, what do you think?”
- Meeting agenda timer.
- Topic drift warning.
- Decision confirmation prompt.
- Action-item ownership prompt.
- Search across meetings.
- Local embeddings for transcript retrieval.
- Repository/document attachment per meeting.
- Notion/Jira/GitHub export adapters.
- Role presets such as architecture reviewer, product reviewer, security reviewer.
- Multi-room support.
- Mobile responsive layout.
- PWA installation.
- User accounts and role-based access.
- Automatic meeting summary after completion.
