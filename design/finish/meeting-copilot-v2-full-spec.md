# Meeting Copilot v2 — Codex Execution Full Specification

## 0. Purpose

This document is the authoritative implementation specification for **Meeting Copilot v2**.

Codex MUST use this document as the primary source of truth and MUST implement the project end to end.

The project is a Docker-first, self-hosted meeting assistant designed for a workstation equipped with an NVIDIA A6000 GPU.

The system MUST provide:

- Live AI Suggestions
- Live Rolling Summary
- Live Decision Tracking
- Live TODO Tracking
- Automatic Meeting Summary
- Next-Step Recommendations
- Decision History
- Project Memory
- Knowledge Base
- Action Tracker
- Multi-language Support
- Web-based Model and Codex Configuration
- Complete Docker Deployment

Codex CLI MUST be the only LLM reasoning engine.

The implementation MUST NOT stop at scaffolding, mock pages, placeholder buttons, or static demos.

---

# 1. Product Definition

## 1.1 Product Name

Meeting Copilot v2

## 1.2 Product Positioning

Meeting Copilot v2 is an AI meeting assistant that listens to meetings, transcribes discussion, identifies useful insights, extracts decisions and tasks, summarizes outcomes, recommends next steps, and builds a persistent project knowledge layer across meetings.

## 1.3 Primary Users

- Software engineering teams
- Project managers
- Technical leads
- Product teams
- Architecture review groups
- DevOps teams
- Internal research and planning teams

## 1.4 Core Product Principle

The system MUST follow this behavior:

```text
Listen continuously
→ transcribe continuously
→ update meeting state
→ trigger Codex only when needed
→ produce structured analysis
→ show suggestions without interrupting
→ require approval before speech
→ persist decisions, actions, and project memory
```

---

# 2. Mandatory Capabilities

The final system MUST implement all of the following.

## 2.1 Live AI Suggestions

The system MUST detect and suggest:

- Missing risks
- Missing requirements
- Contradictions
- Alternative approaches
- Security concerns
- Reliability concerns
- Performance concerns
- Cost concerns
- Operational concerns
- Missing owners
- Missing deadlines
- Missing acceptance criteria
- Missing decisions
- Unresolved questions
- Recommended follow-up questions

Each suggestion MUST include:

- Category
- Suggestion text
- Reason
- Confidence
- Trigger
- Evidence transcript segment IDs
- Created time
- Status
- Related project
- Related meeting

Suggestion statuses:

- proposed
- accepted
- ignored
- edited
- converted_to_decision
- converted_to_action
- converted_to_question
- archived

Required actions:

- Accept
- Ignore
- Edit
- Copy
- Speak
- Convert to Decision
- Convert to Open Question
- Convert to Risk
- Convert to Action Item

## 2.2 Live Rolling Summary

The system MUST maintain a live summary during the meeting.

The live summary MUST include:

- Current topic
- Discussion summary
- Confirmed decisions
- Draft decisions
- Open questions
- Risks
- Action items
- Parking lot
- Unresolved contradictions

The rolling summary MUST update at a configurable interval.

Default:

```yaml
summary_update_interval_seconds: 120
```

## 2.3 Live Decision Tracking

The system MUST detect decisions in real time.

Each decision MUST include:

- ID
- Title
- Description
- Project ID
- Meeting ID
- Owner
- Status
- Confidence
- Timestamp
- Evidence transcript segment IDs
- Version
- Supersedes decision ID
- Superseded by decision ID
- Created by
- Updated by
- Created at
- Updated at

Decision statuses:

- draft
- proposed
- confirmed
- rejected
- superseded
- archived

Decision history MUST be immutable.

A changed decision MUST create a new version or superseding decision.

## 2.4 Live TODO Tracking

The system MUST detect action items in real time.

Each action item MUST include:

- Title
- Description
- Owner
- Due date
- Priority
- Status
- Source meeting
- Source suggestion
- Source decision
- Evidence transcript segment IDs
- Created at
- Updated at

Statuses:

- open
- in_progress
- blocked
- completed
- cancelled
- overdue

Priorities:

- low
- medium
- high
- critical

## 2.5 Meeting Summary

When a meeting ends, the system MUST generate:

- Executive summary
- Technical summary
- Discussion overview
- Decisions
- Draft decisions
- Open questions
- Risks
- Action items
- Parking lot
- Unresolved contradictions
- Next-step recommendations
- Suggested next meeting agenda
- Suggested follow-up participants

Exports:

- Markdown
- JSON
- PDF
- WebVTT
- SRT

## 2.6 Next-Step Recommendations

Codex MUST recommend:

- Immediate next task
- Recommended execution order
- Missing implementation work
- Missing tests
- Missing documentation
- Missing operational work
- Missing monitoring
- Missing validation
- Suggested sprint breakdown
- Suggested owner
- Suggested due date
- Estimated effort
- Dependencies

Each recommendation MUST include:

- title
- rationale
- priority
- effort
- dependencies
- owner suggestion
- source evidence

## 2.7 Decision History

The system MUST provide a decision timeline.

Users MUST be able to:

- Search decisions
- Filter by project
- Filter by status
- Filter by date
- Filter by owner
- View superseded decisions
- View decision evidence
- View related meetings
- View related action items
- Compare decision versions

## 2.8 Project Memory

The system MUST maintain persistent project memory.

Project memory categories:

- Architecture
- APIs
- Data model
- Infrastructure
- Security constraints
- Performance constraints
- Business constraints
- Naming conventions
- Coding conventions
- Deployment conventions
- Known risks
- Lessons learned
- Rejected alternatives
- Glossary
- Stakeholders
- Project goals
- Project non-goals

Codex MUST receive relevant project memory before generating recommendations.

Project memory items MUST include:

- Project ID
- Category
- Title
- Content
- Source meeting
- Source decision
- Confidence
- Status
- Version
- Created at
- Updated at

## 2.9 Knowledge Base

The knowledge base MUST index:

- Meetings
- Transcripts
- Summaries
- Decisions
- Risks
- Questions
- Action items
- Project memory
- Uploaded documents
- Repository metadata
- Exported reports

Search modes:

- Keyword search
- Filtered search
- Full-text search
- Semantic search when embedding provider is configured

Search filters:

- Project
- Meeting
- Date
- Participant
- Topic
- Decision
- Action owner
- Status
- Language
- Source type

## 2.10 Action Tracker

The Action Tracker MUST provide:

- All tasks
- My tasks
- By owner
- By project
- By meeting
- By status
- By due date
- By priority
- Overdue
- Due soon
- Completed

Required actions:

- Create
- Edit
- Assign
- Change status
- Change due date
- Link decision
- Link meeting
- Archive
- Delete

---

# 3. Multi-Language Requirements

## 3.1 Supported Languages

The MVP MUST support:

- Traditional Chinese
- Simplified Chinese
- English
- Japanese
- Korean

Architecture MUST allow additional languages.

## 3.2 Independent Language Settings

The system MUST allow independent configuration for:

- UI language
- Meeting input language
- Secondary meeting language
- Transcript display language
- Translation language
- Suggestion output language
- Summary output language
- Export language
- TTS language

Example:

```text
Meeting input: Japanese
Transcript: Japanese
Suggestions: Traditional Chinese
Summary: Traditional Chinese
TTS: Japanese
```

## 3.3 Language Detection

The system SHOULD support automatic language detection.

The system MUST allow manual override.

## 3.4 Mixed-Language Meetings

The STT pipeline MUST support mixed language, especially:

- Chinese + English technical terms
- Japanese + English technical terms
- Korean + English technical terms

## 3.5 Translation

Translation MUST be optional.

Modes:

- Original transcript only
- Original + translated transcript
- Analyze original
- Analyze translated
- Analyze both

Codex MUST NOT silently replace the original transcript.

## 3.6 Project Glossary

Each project MUST support a glossary.

Glossary entries:

- term
- language
- preferred spelling
- translation
- description
- aliases
- do-not-translate flag

The glossary MUST be injected into STT post-processing and Codex context.

---

# 4. Docker-First Architecture

All primary components MUST run in Docker.

## 4.1 Required Services

```text
docker compose
├── reverse-proxy
├── frontend
├── backend
├── stt-worker
├── codex-worker
├── tts-worker
├── postgres
├── redis
└── monitoring (optional profile)
```

## 4.2 Service Responsibilities

### reverse-proxy

Responsibilities:

- Single entry point
- HTTPS termination
- WebSocket forwarding
- Request size limits
- Security headers
- Static compression

Recommended:

- Nginx or Traefik

### frontend

Responsibilities:

- Setup wizard
- Configuration pages
- Dashboard
- Live meeting
- History
- Decision timeline
- Project memory
- Knowledge base
- Action tracker
- Diagnostics

Technology:

- React
- TypeScript
- Vite
- TanStack Query
- Zod
- WebSocket client
- Web Audio API

### backend

Responsibilities:

- REST API
- WebSocket API
- Authentication
- Authorization
- Session management
- Meeting lifecycle
- Configuration management
- Event routing
- Persistence
- Export generation
- Worker coordination
- Health aggregation

Technology:

- Python 3.12
- FastAPI
- Pydantic v2
- SQLAlchemy 2
- Alembic
- asyncio

### stt-worker

Responsibilities:

- Audio decoding
- Audio buffering
- VAD
- Speech-to-text
- Partial transcripts
- Final transcripts
- Timestamp preservation
- Language detection
- GPU usage

Default engine:

- faster-whisper
- model: large-v3-turbo
- device: cuda
- compute_type: float16

### codex-worker

Responsibilities:

- Install and run Codex CLI
- Manage Codex authentication
- Manage Codex provider configuration
- Receive jobs
- Serialize jobs per meeting
- Build bounded context
- Execute Codex
- Validate output
- Handle timeout
- Handle cancellation
- Redact secrets
- Persist execution metadata

### tts-worker

Responsibilities:

- Optional server-side TTS
- HTTP TTS adapter
- OpenAI-compatible TTS adapter
- Audio streaming
- Voice configuration

Browser SpeechSynthesis MUST remain available as the default fallback.

### postgres

Responsibilities:

- Main relational database
- Full-text search
- Persistent state

### redis

Responsibilities:

- Event bus
- Job queue
- Worker coordination
- Distributed locks
- Cache
- Rate limiting

## 4.3 GPU Allocation

The A6000 GPU MUST primarily serve:

- STT
- Optional TTS
- Optional embeddings

Codex worker MUST NOT require GPU.

Docker Compose MUST use NVIDIA Container Toolkit.

Example requirement:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

## 4.4 Container Security

Every service MUST:

- Run as non-root
- Drop unnecessary capabilities
- Use `no-new-privileges`
- Use read-only root filesystem where practical
- Use tmpfs for temporary files
- Avoid mounting Docker socket
- Avoid host network mode
- Use internal Docker network
- Use explicit volumes
- Redact secrets

The Codex worker MUST:

- Use non-root user
- Mount persistent Codex auth volume
- Mount runtime volume
- Mount repository paths read-only
- Mount only allowlisted paths
- Never mount `/`
- Never mount `/var/run/docker.sock`

---

# 5. Codex CLI Requirements

## 5.1 Reasoning Engine

Codex CLI MUST be the only LLM reasoning engine.

No separate chat LLM API may be introduced.

## 5.2 Codex Authentication

The web UI MUST support:

- Check Codex status
- Start login
- Cancel login
- Logout
- Refresh status
- Test Codex
- View sanitized configuration

Supported authentication methods:

- Existing Codex authentication volume
- Interactive Codex login
- API-key-based provider
- Custom OpenAI-compatible provider

Credentials MUST NOT be stored in application database as plaintext.

## 5.3 Codex Provider Settings

The UI MUST support:

- Provider name
- Base URL
- Model
- API key secret reference
- Timeout
- Retry count
- Profile
- Sandbox policy
- Approval policy
- Network policy
- Working directory policy

## 5.4 Persistent Authentication

Codex auth MUST persist through a Docker named volume.

Example:

```yaml
volumes:
  codex-auth:
```

Mounted at:

```text
/home/codex/.codex
```

## 5.5 Codex Execution Policy

Default:

```yaml
sandbox: read-only
approval_policy: never
network_access: false
repository_access: false
timeout_seconds: 180
max_retries: 1
max_parallel_jobs_per_meeting: 1
```

## 5.6 Codex Worker Job States

```text
queued
preparing_context
running
validating
repairing
completed
failed
timed_out
cancelled
```

## 5.7 Codex Input Schema

```json
{
  "job_id": "uuid",
  "meeting_id": "uuid",
  "project_id": "uuid",
  "job_type": "periodic_analysis",
  "language": {
    "input": "zh-TW",
    "output": "zh-TW"
  },
  "meeting": {
    "title": "string",
    "goal": "string",
    "current_topic": "string",
    "decisions": [],
    "open_questions": [],
    "risks": [],
    "action_items": []
  },
  "project_memory": [],
  "knowledge_context": [],
  "recent_transcript": [],
  "recent_suggestions": [],
  "manual_question": null,
  "review_roles": [],
  "repository_context": {
    "enabled": false,
    "paths": []
  }
}
```

## 5.8 Codex Output Schema

```json
{
  "should_suggest": true,
  "confidence": 0.9,
  "category": "risk",
  "suggestion": "string",
  "reason": "string",
  "follow_up_question": "string",
  "evidence_segment_ids": [],
  "summary_patch": {
    "current_topic": null,
    "discussion_summary": null
  },
  "state_patch": {
    "add_decisions": [],
    "add_open_questions": [],
    "add_risks": [],
    "add_action_items": [],
    "add_parking_lot": [],
    "add_project_memory": []
  },
  "next_steps": []
}
```

## 5.9 JSON Validation

The worker MUST:

- Validate output with JSON Schema
- Reject invalid evidence IDs
- Reject invalid categories
- Reject unknown patch operations
- Enforce length limits
- Perform one repair attempt for invalid JSON
- Fail safely after repair failure

## 5.10 Per-Meeting Concurrency

Only one Codex job may run per meeting.

Redis distributed lock SHOULD be used.

---

# 6. STT Architecture

## 6.1 Default Model

```yaml
engine: faster-whisper
model: large-v3-turbo
device: cuda
compute_type: float16
language: auto
vad_filter: true
beam_size: 5
```

## 6.2 Fallback Models

- medium
- small

## 6.3 Browser Audio Format

Preferred:

```yaml
sample_rate: 16000
channels: 1
encoding: pcm_s16le
chunk_ms: 500
```

Opus MAY be used if server conversion is reliable.

## 6.4 STT Features

MUST support:

- Partial transcript
- Final transcript
- Timestamp
- Language
- Confidence
- Sequence number
- Duplicate overlap removal
- Reconnect
- Lost chunk detection
- Audio backpressure
- Microphone test

## 6.5 Speaker Support

MVP:

- speaker_id schema
- manual rename
- manual merge

Future:

- automatic diarization

Automatic diarization MUST NOT block MVP completion.

## 6.6 A6000 Benchmark

Provide benchmark command measuring:

- Model load time
- Real-time factor
- Peak GPU memory
- Five-minute stability
- Thirty-minute stability
- Error rate

---

# 7. TTS Architecture

## 7.1 Required Adapters

- Browser SpeechSynthesis
- OpenAI-compatible TTS endpoint
- Disabled mode

## 7.2 TTS Settings

- provider
- base URL
- model
- voice
- language
- speed
- volume
- timeout
- retries

## 7.3 Playback Rules

- Auto-speak disabled by default
- User approval required by default
- Ignored suggestion MUST NOT be spoken
- Simultaneous playback MUST be prevented
- Playback MUST be cancellable

---

# 8. Web Pages

## 8.1 Setup Wizard

Steps:

1. System check
2. Codex authentication
3. Codex provider
4. STT setup
5. TTS setup
6. Language setup
7. Microphone test
8. Save and continue

System checks:

- Docker
- Docker Compose
- NVIDIA driver
- NVIDIA Container Toolkit
- GPU model
- GPU memory
- CUDA
- FFmpeg
- Codex CLI
- Database
- Redis
- Disk space

## 8.2 Codex Authentication Page

Show:

- Installed status
- Version
- Authentication status
- Provider
- Profile
- Model
- Last test
- Sanitized error

Actions:

- Check Status
- Start Login
- Cancel Login
- Logout
- Test Codex
- Refresh

## 8.3 Model Provider Page

Roles:

- reasoning
- stt
- tts
- embedding
- reranker

Fields:

- name
- role
- provider type
- base URL
- model
- secret reference
- timeout
- retries
- enabled
- default
- advanced JSON
- health status
- latency

Actions:

- Create
- Edit
- Delete
- Test
- Set Default
- Disable

## 8.4 Main Dashboard

Show:

- Start Meeting
- Active Meetings
- Recent Meetings
- Codex status
- STT status
- TTS status
- GPU usage
- GPU memory
- Queue depth
- Open actions
- Overdue actions
- Recent decisions
- Recent errors

## 8.5 Project Dashboard

Show:

- Project overview
- Project goals
- Project memory
- Recent meetings
- Decision timeline
- Risks
- Open questions
- Action items
- Knowledge documents
- Glossary

## 8.6 Meeting Preparation Page

Fields:

- Project
- Meeting title
- Meeting goal
- Participants
- Agenda
- Input language
- Secondary language
- Suggestion language
- Summary language
- TTS language
- Microphone
- STT provider
- TTS provider
- Codex profile
- Review roles
- Automatic analysis
- Analysis interval
- Suggestion cooldown
- Save audio
- Repository context
- Reference documents

## 8.7 Live Meeting Page

Header:

- Title
- Project
- Elapsed time
- Meeting status
- STT status
- Codex status
- Queue state
- Start
- Pause
- Resume
- End

Transcript panel:

- Partial transcript
- Final transcript
- Timestamp
- Speaker
- Language
- Translation
- Edit
- Pin
- Search
- Auto-scroll

AI panel:

- Suggestions
- Manual Ask Codex
- Codex job state
- Reason
- Confidence
- Evidence

Meeting state panel:

- Current topic
- Rolling summary
- Decisions
- Draft decisions
- Questions
- Risks
- TODO
- Parking lot

## 8.8 Meeting Summary Page

Show:

- Executive summary
- Technical summary
- Decisions
- Questions
- Risks
- TODO
- Next steps
- Suggested agenda
- Export buttons

## 8.9 Meeting History

Features:

- List
- Search
- Filters
- Open detail
- Delete
- Export
- Re-run analysis

## 8.10 Decision History

Features:

- Timeline
- Search
- Compare versions
- Related meetings
- Related tasks
- Superseded decisions

## 8.11 Project Memory

Features:

- List
- Search
- Edit
- Archive
- Version
- Source
- Category

## 8.12 Knowledge Base

Features:

- Keyword search
- Full-text search
- Semantic search if enabled
- Filters
- Source preview
- Related decisions
- Related meetings

## 8.13 Action Tracker

Views:

- All
- Mine
- Overdue
- Due soon
- In progress
- Blocked
- Completed

## 8.14 Diagnostics

Show:

- Backend
- Database
- Redis
- Codex
- STT
- TTS
- GPU
- WebSocket
- Queue
- Latency
- Recent sanitized events

Tests:

- Five-second recording
- STT test
- Codex test
- TTS test
- Provider test
- Database migration test

---

# 9. API Requirements

Implement typed REST APIs.

## 9.1 System

```text
GET /api/health
GET /api/system/status
GET /api/system/gpu
GET /api/system/diagnostics
```

## 9.2 Codex

```text
GET  /api/codex/status
POST /api/codex/login/start
POST /api/codex/login/cancel
POST /api/codex/logout
POST /api/codex/test
```

## 9.3 Providers

```text
GET    /api/providers
POST   /api/providers
GET    /api/providers/{id}
PUT    /api/providers/{id}
DELETE /api/providers/{id}
POST   /api/providers/{id}/test
POST   /api/providers/{id}/set-default
```

## 9.4 Projects

```text
GET    /api/projects
POST   /api/projects
GET    /api/projects/{id}
PUT    /api/projects/{id}
DELETE /api/projects/{id}
```

## 9.5 Meetings

```text
POST   /api/meetings
GET    /api/meetings
GET    /api/meetings/{id}
POST   /api/meetings/{id}/start
POST   /api/meetings/{id}/pause
POST   /api/meetings/{id}/resume
POST   /api/meetings/{id}/end
DELETE /api/meetings/{id}
```

## 9.6 Meeting WebSockets

```text
WS /api/meetings/{id}/audio
WS /api/meetings/{id}/events
```

## 9.7 Codex Jobs

```text
POST /api/meetings/{id}/ask
POST /api/meetings/{id}/analyze
GET  /api/codex-runs/{id}
POST /api/codex-runs/{id}/cancel
```

## 9.8 Suggestions

```text
POST /api/suggestions/{id}/accept
POST /api/suggestions/{id}/ignore
POST /api/suggestions/{id}/edit
POST /api/suggestions/{id}/speak
POST /api/suggestions/{id}/to-decision
POST /api/suggestions/{id}/to-action
POST /api/suggestions/{id}/to-question
POST /api/suggestions/{id}/to-risk
```

## 9.9 Decisions

```text
GET    /api/decisions
POST   /api/decisions
GET    /api/decisions/{id}
PUT    /api/decisions/{id}
POST   /api/decisions/{id}/confirm
POST   /api/decisions/{id}/reject
POST   /api/decisions/{id}/supersede
```

## 9.10 Actions

```text
GET    /api/actions
POST   /api/actions
GET    /api/actions/{id}
PUT    /api/actions/{id}
DELETE /api/actions/{id}
```

## 9.11 Project Memory

```text
GET    /api/projects/{id}/memory
POST   /api/projects/{id}/memory
PUT    /api/project-memory/{id}
DELETE /api/project-memory/{id}
```

## 9.12 Knowledge Base

```text
GET  /api/knowledge/search
POST /api/knowledge/documents
GET  /api/knowledge/documents/{id}
DELETE /api/knowledge/documents/{id}
```

## 9.13 Exports

```text
POST /api/meetings/{id}/export/markdown
POST /api/meetings/{id}/export/json
POST /api/meetings/{id}/export/pdf
POST /api/meetings/{id}/export/vtt
POST /api/meetings/{id}/export/srt
```

---

# 10. Event Protocol

Envelope:

```json
{
  "event_id": "uuid",
  "meeting_id": "uuid",
  "project_id": "uuid",
  "type": "transcript.final",
  "sequence": 1,
  "source": "stt-worker",
  "created_at": "ISO-8601",
  "payload": {}
}
```

Required event types:

```text
project.created
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
translation.completed
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
decision.created
decision.confirmed
decision.superseded
action.created
action.updated
risk.created
question.created
summary.updated
project_memory.created
tts.started
tts.completed
tts.failed
system.warning
```

Sequences MUST be monotonically increasing per meeting.

---

# 11. Database Schema

Use PostgreSQL in normal Docker deployment.

SQLite MAY be supported only for lightweight development.

Required tables:

## app_settings

- id
- key
- value_json
- secret_reference
- created_at
- updated_at

## users

- id
- email
- display_name
- role
- created_at
- updated_at

## projects

- id
- name
- description
- goals
- non_goals
- default_language
- created_at
- updated_at

## project_glossary

- id
- project_id
- term
- language
- preferred_spelling
- translation
- description
- aliases_json
- do_not_translate
- created_at
- updated_at

## model_providers

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

## meetings

- id
- project_id
- title
- goal
- agenda
- language
- secondary_language
- suggestion_language
- summary_language
- tts_language
- status
- started_at
- ended_at
- configuration_json
- save_audio
- repository_context_enabled
- created_at
- updated_at

## participants

- id
- meeting_id
- display_name
- speaker_label
- email
- created_at

## transcript_segments

- id
- meeting_id
- sequence
- speaker_id
- language
- translated_language
- start_ms
- end_ms
- text
- translated_text
- confidence
- is_final
- is_edited
- created_at
- updated_at

## meeting_states

- id
- meeting_id
- version
- current_topic
- rolling_summary
- state_json
- source
- created_at

## codex_runs

- id
- meeting_id
- project_id
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

## suggestions

- id
- meeting_id
- project_id
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

## decisions

- id
- project_id
- meeting_id
- title
- description
- owner
- status
- confidence
- version
- supersedes_id
- superseded_by_id
- evidence_segment_ids_json
- created_at
- updated_at

## open_questions

- id
- project_id
- meeting_id
- content
- status
- owner
- evidence_segment_ids_json
- created_at
- updated_at

## risks

- id
- project_id
- meeting_id
- content
- severity
- probability
- status
- owner
- evidence_segment_ids_json
- created_at
- updated_at

## action_items

- id
- project_id
- meeting_id
- title
- description
- owner
- due_at
- priority
- status
- linked_decision_id
- evidence_segment_ids_json
- created_at
- updated_at

## project_memory

- id
- project_id
- category
- title
- content
- source_meeting_id
- source_decision_id
- confidence
- status
- version
- created_at
- updated_at

## knowledge_documents

- id
- project_id
- source_type
- title
- content
- language
- metadata_json
- created_at
- updated_at

## events

- id
- meeting_id
- project_id
- sequence
- type
- source
- payload_json
- created_at

## audio_chunks

- id
- meeting_id
- sequence
- path
- start_ms
- end_ms
- checksum
- status
- created_at

Add foreign keys, indexes, uniqueness constraints, and full-text indexes.

---

# 12. Trigger Engine

The trigger engine MUST use deterministic logic before Codex.

Required triggers:

- Manual Ask Codex
- Direct assistant mention
- Explicit question
- Periodic analysis
- Decision keywords
- Long discussion without decision
- Repeated topic
- Contradiction signal
- Silence after question
- Meeting end
- User requests summary
- User requests next steps

Required suppressors:

- Insufficient transcript
- Meeting paused
- Codex already running
- Cooldown active
- Duplicate recent suggestion
- Low STT confidence
- Automatic analysis disabled

Default:

```yaml
periodic_analysis_seconds: 120
minimum_new_characters: 300
codex_cooldown_seconds: 60
suggestion_cooldown_seconds: 180
maximum_recent_transcript_minutes: 10
maximum_recent_transcript_characters: 12000
automatic_analysis_enabled: true
```

---

# 13. Project Memory and Knowledge Retrieval

Before Codex runs, the backend MUST retrieve:

- Relevant project memory
- Recent decisions
- Open actions
- Open questions
- Relevant knowledge documents
- Recent meeting summaries

Context retrieval MUST be bounded.

The backend MUST NOT send the entire project history on every request.

Retrieval ranking SHOULD consider:

- Project
- Topic
- Keywords
- Decision relationship
- Recency
- Semantic similarity when embeddings exist

---

# 14. Security

MUST implement:

- Localhost-only default binding
- Authentication for remote access
- Role-based authorization readiness
- CSRF protection
- WebSocket origin validation
- Audio frame size limit
- Upload size limit
- Path traversal prevention
- Repository path allowlist
- Shell argument arrays
- No raw shell concatenation
- Secret redaction
- Docker secrets
- No plaintext credentials
- Audit events for configuration changes
- Complete meeting deletion
- Independent audio deletion
- Explicit consent before audio saving
- Sanitized diagnostic bundles

---

# 15. Reliability

MUST implement:

- WebSocket reconnection
- Frontend state recovery
- Idempotency keys
- Database transactions
- Worker retries for transient errors
- Codex timeout
- Codex cancellation
- One Codex job per meeting
- Stale job recovery
- Graceful shutdown
- Readiness endpoints
- Liveness endpoints
- Interrupted meeting recovery
- Transcript persistence before downstream processing

---

# 16. Observability

Required metrics:

- Active meetings
- Audio chunks received
- Audio chunks dropped
- STT latency
- STT real-time factor
- STT queue depth
- Codex queue depth
- Codex latency
- Codex success rate
- Codex failure rate
- Codex timeout rate
- Suggestions generated
- Suggestions accepted
- Suggestions ignored
- Duplicate suggestions suppressed
- TTS latency
- GPU utilization
- GPU memory
- Database latency
- Redis latency
- WebSocket connections

Use structured JSON logs.

Every request and job MUST have correlation IDs.

---

# 17. Repository Structure

```text
meeting-copilot/
├── README.md
├── AGENTS.md
├── LICENSE
├── .env.example
├── .gitignore
├── docker-compose.yml
├── docker-compose.dev.yml
├── Makefile
├── docs/
│   ├── architecture.md
│   ├── deployment.md
│   ├── codex-auth.md
│   ├── providers.md
│   ├── security.md
│   ├── operations.md
│   ├── multilingual.md
│   └── troubleshooting.md
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   └── src/
├── backend/
│   ├── Dockerfile
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
├── workers/
│   ├── stt/
│   │   ├── Dockerfile
│   │   └── app/
│   ├── codex/
│   │   ├── Dockerfile
│   │   └── app/
│   └── tts/
│       ├── Dockerfile
│       └── app/
├── reverse-proxy/
│   ├── Dockerfile
│   └── nginx.conf
├── schemas/
│   ├── codex-request.schema.json
│   ├── codex-response.schema.json
│   └── event.schema.json
├── scripts/
│   ├── bootstrap.sh
│   ├── check-system.sh
│   ├── benchmark-stt.py
│   ├── smoke-test.sh
│   └── seed-dev-data.py
└── runtime/
    └── .gitkeep
```

---

# 18. Docker Compose Requirements

The final `docker-compose.yml` MUST include:

- reverse-proxy
- frontend
- backend
- stt-worker
- codex-worker
- tts-worker
- postgres
- redis

Requirements:

- Health checks
- Named volumes
- Internal network
- GPU allocation
- Persistent Codex auth
- Persistent database
- Persistent meeting data
- Persistent project memory
- No Docker socket mount
- Non-root users
- Restart policy
- Secret injection
- Dependency conditions

Named volumes:

```text
postgres-data
redis-data
codex-auth
meeting-data
audio-data
model-cache
```

---

# 19. Testing

## 19.1 Unit Tests

- Trigger logic
- Cooldown
- Transcript deduplication
- Translation state handling
- Codex request generation
- Codex output validation
- State patch validation
- Suggestion deduplication
- Decision versioning
- Project memory retrieval
- Action status transitions
- Secret redaction
- Path allowlisting
- Provider validation

## 19.2 Integration Tests

- Project creation
- Meeting creation
- Meeting start/pause/resume/end
- WebSocket transcript flow
- Mock STT
- Mock Codex
- Codex timeout
- Invalid Codex JSON
- Codex cancellation
- Suggestion accept/ignore
- Decision confirmation
- Decision supersede
- Action creation
- Meeting summary generation
- Project memory persistence
- Knowledge search
- Exports
- Restart recovery

## 19.3 End-to-End Test

Automate:

1. Open setup wizard
2. Configure mock providers
3. Create project
4. Add glossary
5. Start meeting
6. Stream fixture audio
7. Display transcript
8. Trigger Codex
9. Show suggestion
10. Accept suggestion
11. Create decision
12. Create action
13. End meeting
14. Generate summary
15. Generate next steps
16. Export Markdown
17. Open decision history
18. Search knowledge base
19. Verify project memory

## 19.4 A6000 Smoke Test

Verify:

- GPU detected
- CUDA available
- STT model loads
- Audio transcribes faster than real time
- GPU memory stable
- Thirty-minute stream stable
- Codex worker completes structured test
- TTS test works
- No secrets in logs

---

# 20. Acceptance Criteria

The project is complete only when:

1. `docker compose up -d` starts the full platform.
2. Setup wizard works.
3. Codex login works in Docker.
4. Codex authentication persists after restart.
5. Custom Codex provider/base URL/model can be configured.
6. STT runs on A6000.
7. Microphone audio reaches STT.
8. Live transcript appears.
9. Multi-language configuration works.
10. Live rolling summary works.
11. Live suggestions work.
12. Live decisions work.
13. Live TODO extraction works.
14. Meeting summary is generated.
15. Next-step recommendations are generated.
16. Decision history is searchable.
17. Project memory persists.
18. Knowledge base search works.
19. Action Tracker works.
20. Markdown export works.
21. JSON export works.
22. PDF export works.
23. VTT export works.
24. SRT export works.
25. Diagnostics page works.
26. Health checks work.
27. No placeholder buttons remain.
28. No secrets appear in UI or logs.
29. Required tests pass.
30. README contains exact deployment instructions.

---

# 21. Implementation Sequence

Codex MUST implement in this order.

## Milestone 1 — Foundation

- Repository
- Docker Compose
- Reverse proxy
- Frontend
- Backend
- PostgreSQL
- Redis
- Health checks
- GPU detection

## Milestone 2 — Configuration

- Setup wizard
- Codex status
- Codex login
- Provider registry
- Language settings
- Secret handling

## Milestone 3 — Projects

- Project CRUD
- Project dashboard
- Glossary
- Project memory schema

## Milestone 4 — Audio and STT

- Browser microphone
- Audio WebSocket
- STT worker
- Transcript
- Language handling
- Persistence
- Benchmark

## Milestone 5 — Codex Worker

- Dockerized Codex
- Persistent auth
- Queue
- Locks
- Context building
- JSON Schema
- Timeout
- Cancellation

## Milestone 6 — Live Meeting Intelligence

- Trigger engine
- Suggestions
- Rolling summary
- Decisions
- Questions
- Risks
- TODO
- Parking lot

## Milestone 7 — Meeting Completion

- Meeting summary
- Next steps
- Suggested agenda
- Exports

## Milestone 8 — Long-Term Knowledge

- Decision history
- Project memory
- Knowledge base
- Search
- Action tracker

## Milestone 9 — Multilingual

- UI languages
- Transcript languages
- Output languages
- Translation
- Glossary enforcement
- TTS language

## Milestone 10 — Hardening

- Security
- Reliability
- Diagnostics
- Metrics
- E2E
- A6000 smoke test
- Documentation

After each milestone:

- Run tests
- Fix failures
- Update README
- Update architecture documentation
- Do not continue with failing required tests

---

# 22. Codex Execution Instructions

Codex MUST follow these rules:

1. Read this entire specification before coding.
2. Implement the project end to end.
3. Do not stop after scaffolding.
4. Do not leave placeholder pages.
5. Do not leave non-functional buttons.
6. Use Docker-first deployment.
7. Install Codex CLI inside the Codex worker container.
8. Use Codex CLI as the only LLM reasoning engine.
9. Use local STT on the A6000.
10. Use strict JSON Schemas.
11. Run tests after every milestone.
12. Fix errors before continuing.
13. Document exact startup commands.
14. Never expose credentials.
15. Make reasonable implementation decisions without waiting for clarification.
16. Prefer working software over speculative abstractions.
17. Preserve historical decisions.
18. Persist project memory.
19. Ensure meeting functions still work when Codex fails.
20. Return a complete final implementation report.

---

# 23. Required Final Report

Codex MUST provide:

1. Architecture summary
2. Repository tree
3. Services implemented
4. Pages implemented
5. APIs implemented
6. Database migrations
7. Docker startup commands
8. Codex authentication steps
9. Provider configuration steps
10. STT configuration
11. TTS configuration
12. Multi-language configuration
13. Test commands
14. Test results
15. A6000 benchmark results
16. Known limitations
17. Security assumptions
18. Remaining optional enhancements

Do not claim completion unless the feature is implemented and tested.
