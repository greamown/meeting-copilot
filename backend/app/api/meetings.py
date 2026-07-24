import asyncio
import hashlib
import io
import json
import os
import shutil
import struct
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import allowlisted_path
from app.db.base import (
    ActionItem,
    AudioChunk,
    CodexRun,
    Decision,
    IdempotencyRecord,
    Meeting,
    ModelProvider,
    OpenQuestion,
    Participant,
    Project,
    ProjectGlossary,
    Risk,
    Suggestion,
    TranscriptSegment,
)
from app.db.session import SessionLocal, get_db
from app.schemas.meeting import (
    AskRequest,
    CommandResponse,
    EngineRunResponse,
    ManualSuggestionCreate,
    MeetingCreate,
    MeetingDetail,
    MeetingRead,
    StateItemCreate,
    SuggestionEdit,
    SuggestionRead,
    TranscriptEdit,
    TranscriptRead,
)
from app.services.auth import remote_auth_applies, websocket_identity, websocket_origin_allowed
from app.services.engine import build_request, get_project_context, manager
from app.services.events import emit, hub
from app.services.glossary import normalize_transcript
from app.services.stt import create_stt_service
from app.services.trigger import (
    TriggerContext,
    accumulate_new_characters,
    decide_trigger,
    merge_overlap,
)

router = APIRouter()


async def require_meeting(db: AsyncSession, meeting_id: str) -> Meeting:
    row = await db.get(Meeting, meeting_id)
    if not row:
        raise HTTPException(404, "Meeting not found")
    return row


def public_row(row: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: getattr(row, field) for field in fields}


@router.post("/meetings", response_model=MeetingRead, status_code=201)
async def create_meeting(
    payload: MeetingCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Meeting:
    idempotency_key = request.headers.get("X-Idempotency-Key")
    if idempotency_key and len(idempotency_key) > 200:
        raise HTTPException(422, "Idempotency key is too long")
    request_hash = hashlib.sha256(
        payload.model_dump_json(exclude_none=False).encode()
    ).hexdigest()
    if idempotency_key:
        existing = await db.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.scope == "meeting.create",
                IdempotencyRecord.key == idempotency_key,
            )
        )
        if existing:
            if existing.request_hash != request_hash:
                raise HTTPException(409, "Idempotency key was already used with another request")
            prior = await db.get(Meeting, existing.resource_id)
            if prior:
                return prior
    if payload.project_id and not await db.get(Project, payload.project_id):
        raise HTTPException(422, "Project not found")
    repository_path = None
    if payload.repository_context_enabled:
        repository_path = str(
            allowlisted_path(payload.repository_path or "", settings.repository_roots)
        )
    config = payload.model_dump(
        mode="json",
        exclude={
            "title",
            "project_id",
            "goal",
            "language",
            "participants",
            "repository_context_enabled",
            "repository_path",
            "save_audio",
        },
    )
    config["state"] = {
        "current_topic": "",
        "decisions": [],
        "open_questions": [],
        "risks": [],
        "action_items": [],
        "parking_lot": [],
        "last_codex_run_at": None,
        "last_suggestion_at": None,
        "new_transcript_characters": 0,
        "version": 1,
    }
    row = Meeting(
        project_id=payload.project_id,
        title=payload.title,
        goal=payload.goal,
        language=payload.language,
        configuration_json=config,
        audio_saved=payload.save_audio,
        repository_context_enabled=payload.repository_context_enabled,
        repository_path=repository_path,
    )
    db.add(row)
    await db.flush()
    for index, name in enumerate(payload.participants):
        db.add(
            Participant(meeting_id=row.id, display_name=name, speaker_label=f"speaker-{index + 1}")
        )
    await emit(db, row.id, "meeting.created", "meeting-api", {"title": row.title})
    if idempotency_key:
        db.add(
            IdempotencyRecord(
                scope="meeting.create",
                key=idempotency_key,
                request_hash=request_hash,
                resource_type="meeting",
                resource_id=row.id,
            )
        )
    await db.commit()
    await db.refresh(row)
    return row


@router.get("/meetings", response_model=list[MeetingRead])
async def list_meetings(
    status: str | None = None, title: str | None = None, db: AsyncSession = Depends(get_db)
) -> list[Meeting]:
    query = select(Meeting).order_by(desc(Meeting.created_at))
    if status:
        query = query.where(Meeting.status == status)
    if title:
        query = query.where(Meeting.title.ilike(f"%{title}%"))
    return list((await db.scalars(query)).all())


@router.get("/meetings/{meeting_id}", response_model=MeetingDetail)
async def get_meeting(meeting_id: str, db: AsyncSession = Depends(get_db)) -> MeetingDetail:
    meeting = await require_meeting(db, meeting_id)
    transcripts = list(
        (
            await db.scalars(
                select(TranscriptSegment)
                .where(TranscriptSegment.meeting_id == meeting_id)
                .order_by(TranscriptSegment.sequence)
            )
        ).all()
    )
    suggestions = list(
        (
            await db.scalars(
                select(Suggestion)
                .where(Suggestion.meeting_id == meeting_id)
                .order_by(desc(Suggestion.created_at))
            )
        ).all()
    )
    decisions = list(
        (await db.scalars(select(Decision).where(Decision.meeting_id == meeting_id))).all()
    )
    questions = list(
        (await db.scalars(select(OpenQuestion).where(OpenQuestion.meeting_id == meeting_id))).all()
    )
    risks = list((await db.scalars(select(Risk).where(Risk.meeting_id == meeting_id))).all())
    actions = list(
        (await db.scalars(select(ActionItem).where(ActionItem.meeting_id == meeting_id))).all()
    )
    runs = list(
        (
            await db.scalars(
                select(CodexRun)
                .where(CodexRun.meeting_id == meeting_id)
                .order_by(desc(CodexRun.created_at))
            )
        ).all()
    )
    item_fields = ("id", "content", "source", "source_suggestion_id", "created_at", "updated_at")
    run_fields = (
        "id",
        "job_type",
        "trigger",
        "status",
        "profile",
        "model",
        "provider",
        "sanitized_stderr",
        "started_at",
        "ended_at",
        "duration_ms",
        "created_at",
    )
    return MeetingDetail(
        meeting=MeetingRead.model_validate(meeting),
        transcripts=[TranscriptRead.model_validate(row) for row in transcripts],
        suggestions=[SuggestionRead.model_validate(row) for row in suggestions],
        decisions=[public_row(row, item_fields) for row in decisions],
        open_questions=[public_row(row, item_fields + ("status",)) for row in questions],
        risks=[public_row(row, item_fields + ("status",)) for row in risks],
        action_items=[
            public_row(row, item_fields + ("owner", "due_at", "status")) for row in actions
        ],
        codex_runs=[public_row(row, run_fields) for row in runs],
    )


async def transition(
    db: AsyncSession, meeting_id: str, allowed: set[str], target: str, event_type: str
) -> Meeting:
    row = await require_meeting(db, meeting_id)
    if row.status not in allowed:
        raise HTTPException(409, f"Cannot {target} meeting from {row.status}")
    row.status = target
    if target == "active" and not row.started_at:
        row.started_at = datetime.now(UTC)
    if target == "ended":
        row.ended_at = datetime.now(UTC)
    await emit(db, meeting_id, event_type, "meeting-api", {})
    await db.commit()
    await db.refresh(row)
    return row


@router.post("/meetings/{meeting_id}/start", response_model=CommandResponse)
async def start(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
) -> CommandResponse:
    meeting = await transition(
        db, meeting_id, {"draft", "interrupted"}, "active", "meeting.started"
    )
    return CommandResponse(meeting=MeetingRead.model_validate(meeting))


@router.post("/meetings/{meeting_id}/pause", response_model=CommandResponse)
async def pause(meeting_id: str, db: AsyncSession = Depends(get_db)) -> CommandResponse:
    return CommandResponse(
        meeting=MeetingRead.model_validate(
            await transition(db, meeting_id, {"active"}, "paused", "meeting.paused")
        )
    )


@router.post("/meetings/{meeting_id}/resume", response_model=CommandResponse)
async def resume(meeting_id: str, db: AsyncSession = Depends(get_db)) -> CommandResponse:
    return CommandResponse(
        meeting=MeetingRead.model_validate(
            await transition(db, meeting_id, {"paused"}, "active", "meeting.resumed")
        )
    )


@router.post("/meetings/{meeting_id}/end", response_model=CommandResponse)
async def end(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CommandResponse:
    meeting = await transition(
        db, meeting_id, {"active", "paused", "interrupted"}, "ended", "meeting.ended"
    )
    try:
        await request_codex(meeting_id, "meeting_end", "final_summary", None, db, settings)
    except HTTPException as exc:
        if exc.status_code != 409:
            await emit(
                db,
                meeting_id,
                "system.warning",
                "meeting-api",
                {"message": "Final summary could not be queued"},
            )
            await db.commit()
    return CommandResponse(meeting=MeetingRead.model_validate(meeting))


@router.delete("/meetings/{meeting_id}", status_code=204)
async def delete_meeting(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> None:
    row = await require_meeting(db, meeting_id)
    await db.delete(row)
    await db.commit()
    directory = (settings.runtime_dir / "meetings" / meeting_id).resolve()
    meetings_root = (settings.runtime_dir / "meetings").resolve()
    if directory.is_relative_to(meetings_root):
        await asyncio.to_thread(shutil.rmtree, directory, True)


def stored_audio_file(chunk: AudioChunk, runtime_root: Path) -> Path | None:
    """Resolve a chunk to an on-disk file, refusing anything outside the runtime directory."""
    if not chunk.path:
        return None
    path = Path(chunk.path).resolve()
    return path if path.is_relative_to(runtime_root) and path.is_file() else None


def wav_header(data_bytes: int) -> bytes:
    # Chunks are the raw 16 kHz mono s16le stream the browser worklet sends; only a header is
    # missing to make them playable.
    return (
        b"RIFF"
        + struct.pack("<I", 36 + data_bytes)
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, 16_000, 32_000, 2, 16)
        + b"data"
        + struct.pack("<I", data_bytes)
    )


@router.get("/meetings/{meeting_id}/audio")
async def download_audio(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    await require_meeting(db, meeting_id)
    runtime_root = settings.runtime_dir.resolve()
    chunks = await db.scalars(
        select(AudioChunk)
        .where(AudioChunk.meeting_id == meeting_id, AudioChunk.path.is_not(None))
        .order_by(AudioChunk.sequence)
    )
    files = (stored_audio_file(row, runtime_root) for row in chunks.all())
    paths = [file for file in files if file]
    if not paths:
        raise HTTPException(404, "This meeting has no stored audio")
    total = sum(path.stat().st_size for path in paths)

    def stream() -> Iterator[bytes]:
        yield wav_header(total)
        for path in paths:
            yield path.read_bytes()

    # ponytail: no Range support, so the browser can only seek inside what it has buffered.
    # Add a 206 branch if scrubbing long recordings becomes a real complaint.
    return StreamingResponse(
        stream(),
        media_type="audio/wav",
        headers={
            "Content-Length": str(total + 44),
            "Content-Disposition": f'inline; filename="{meeting_id}.wav"',
        },
    )


@router.delete("/meetings/{meeting_id}/audio", status_code=204)
async def delete_audio(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> None:
    meeting = await require_meeting(db, meeting_id)
    runtime_root = settings.runtime_dir.resolve()
    chunks = list(
        (await db.scalars(select(AudioChunk).where(AudioChunk.meeting_id == meeting_id))).all()
    )
    for chunk in chunks:
        path = stored_audio_file(chunk, runtime_root)
        if path:
            path.unlink()
        await db.delete(chunk)
    meeting.audio_saved = False
    await db.commit()


@router.patch("/transcripts/{segment_id}", response_model=TranscriptRead)
async def edit_transcript(
    segment_id: str, payload: TranscriptEdit, db: AsyncSession = Depends(get_db)
) -> TranscriptSegment:
    row = await db.get(TranscriptSegment, segment_id)
    if not row:
        raise HTTPException(404, "Transcript segment not found")
    row.text, row.speaker_id, row.is_edited = payload.text, payload.speaker_id, True
    if payload.is_pinned is not None:
        row.is_pinned = payload.is_pinned
    await emit(db, row.meeting_id, "transcript.edited", "user", {"segment_id": row.id})
    await db.commit()
    await db.refresh(row)
    return row


async def request_codex(
    meeting_id: str,
    trigger: str,
    job_type: str,
    question: str | None,
    db: AsyncSession,
    settings: Settings,
) -> EngineRunResponse:
    meeting = await require_meeting(db, meeting_id)
    active = await db.scalar(
        select(func.count())
        .select_from(CodexRun)
        .where(
            CodexRun.meeting_id == meeting_id,
            CodexRun.status.in_(["queued", "preparing_context", "running", "validating"]),
        )
    )
    if active:
        raise HTTPException(409, "A Codex job is already active for this meeting")
    transcripts = list(
        (
            await db.scalars(
                select(TranscriptSegment)
                .where(
                    TranscriptSegment.meeting_id == meeting_id, TranscriptSegment.is_final.is_(True)
                )
                .order_by(desc(TranscriptSegment.sequence))
                .limit(100)
            )
        ).all()
    )[::-1]
    suggestions = list(
        (
            await db.scalars(
                select(Suggestion)
                .where(Suggestion.meeting_id == meeting_id)
                .order_by(desc(Suggestion.created_at))
                .limit(20)
            )
        ).all()
    )
    memory, glossary, knowledge = await get_project_context(db, meeting)
    request = build_request(
        meeting, transcripts, suggestions, job_type, question, memory, glossary, knowledge
    )
    engine = meeting.configuration_json.get("analysis_engine") or settings.analysis_engine
    claude = engine == "claude"
    run = CodexRun(
        meeting_id=meeting_id,
        job_type=job_type,
        trigger=trigger,
        status="queued",
        profile=None if claude else (meeting.configuration_json.get("codex_profile") or settings.codex_profile),
        model=settings.claude_model if claude else settings.codex_model,
        provider="claude_code" if claude else "codex_cli",
        request_json=request,
    )
    db.add(run)
    await db.flush()
    await emit(
        db, meeting_id, "codex.queued", "meeting-api", {"run_id": run.id, "trigger": trigger}
    )
    await db.commit()
    manager.enqueue(run.id, meeting_id, settings, SessionLocal)
    return EngineRunResponse(run_id=run.id, status="queued")


@router.post("/meetings/{meeting_id}/ask", response_model=EngineRunResponse)
async def ask(
    meeting_id: str,
    payload: AskRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> EngineRunResponse:
    return await request_codex(
        meeting_id, "manual_ask", "manual_ask", payload.question, db, settings
    )


@router.post("/meetings/{meeting_id}/analyze", response_model=EngineRunResponse)
async def analyze(
    meeting_id: str, db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)
) -> EngineRunResponse:
    return await request_codex(
        meeting_id, "manual_analysis", "periodic_analysis", None, db, settings
    )


@router.post("/codex-runs/{run_id}/cancel")
async def cancel_run(
    run_id: str, db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)
) -> dict[str, Any]:
    run = await db.get(CodexRun, run_id)
    if not run:
        raise HTTPException(404, "Codex run not found")
    cancelled = await manager.cancel(run_id, settings)
    if run.status in ("queued", "preparing_context") or cancelled:
        run.status = "cancelled"
        await emit(db, run.meeting_id, "codex.cancelled", "user", {"run_id": run.id})
        await db.commit()
        return {"cancelled": True}
    return {"cancelled": False, "status": run.status}


@router.get("/codex-runs/{run_id}")
async def get_codex_run(run_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    run = await db.get(CodexRun, run_id)
    if not run:
        raise HTTPException(404, "Codex run not found")
    return public_row(
        run,
        (
            "id",
            "meeting_id",
            "job_type",
            "trigger",
            "status",
            "profile",
            "model",
            "provider",
            "response_json",
            "sanitized_stderr",
            "started_at",
            "ended_at",
            "duration_ms",
            "retry_count",
            "created_at",
        ),
    )


@router.post(
    "/meetings/{meeting_id}/suggestions", response_model=SuggestionRead, status_code=201
)
async def create_manual_suggestion(
    meeting_id: str,
    payload: ManualSuggestionCreate,
    db: AsyncSession = Depends(get_db),
) -> Suggestion:
    await require_meeting(db, meeting_id)
    row = Suggestion(
        meeting_id=meeting_id,
        category=payload.category,
        content=payload.content,
        reason=payload.reason,
        confidence=1,
        trigger="manual_participant",
        status="new",
        evidence_segment_ids_json=[],
    )
    db.add(row)
    await db.flush()
    await emit(
        db,
        meeting_id,
        "suggestion.created",
        "user",
        {"suggestion_id": row.id, "category": row.category, "manual": True},
    )
    await db.commit()
    await db.refresh(row)
    return row


async def suggestion_action(
    suggestion_id: str, status: Literal["accepted", "ignored"], db: AsyncSession
) -> Suggestion:
    row = await db.get(Suggestion, suggestion_id)
    if not row:
        raise HTTPException(404, "Suggestion not found")
    row.status = status
    await emit(db, row.meeting_id, f"suggestion.{status}", "user", {"suggestion_id": row.id})
    await db.commit()
    await db.refresh(row)
    return row


@router.post("/suggestions/{suggestion_id}/accept", response_model=SuggestionRead)
async def accept_suggestion(suggestion_id: str, db: AsyncSession = Depends(get_db)) -> Suggestion:
    return await suggestion_action(suggestion_id, "accepted", db)


@router.post("/suggestions/{suggestion_id}/ignore", response_model=SuggestionRead)
async def ignore_suggestion(suggestion_id: str, db: AsyncSession = Depends(get_db)) -> Suggestion:
    return await suggestion_action(suggestion_id, "ignored", db)


@router.post("/suggestions/{suggestion_id}/edit", response_model=SuggestionRead)
async def edit_suggestion(
    suggestion_id: str, payload: SuggestionEdit, db: AsyncSession = Depends(get_db)
) -> Suggestion:
    row = await db.get(Suggestion, suggestion_id)
    if not row:
        raise HTTPException(404, "Suggestion not found")
    row.content = payload.content
    row.status = "edited"
    await emit(db, row.meeting_id, "suggestion.edited", "user", {"suggestion_id": row.id})
    await db.commit()
    await db.refresh(row)
    return row


async def convert_suggestion(
    suggestion_id: str,
    kind: Literal["decision", "action_item", "open_question", "risk"],
    db: AsyncSession,
) -> dict[str, Any]:
    suggestion = await db.get(Suggestion, suggestion_id)
    if not suggestion:
        raise HTTPException(404, "Suggestion not found")
    meeting = await require_meeting(db, suggestion.meeting_id)
    model: Any = {
        "decision": Decision,
        "action_item": ActionItem,
        "open_question": OpenQuestion,
        "risk": Risk,
    }[kind]
    existing = await db.scalar(
        select(model).where(model.source_suggestion_id == suggestion.id)
    )
    if existing:
        return public_row(existing, ("id", "meeting_id", "content", "source", "created_at"))
    values: dict[str, Any] = {
        "meeting_id": meeting.id,
        "project_id": meeting.project_id,
        "content": suggestion.content,
        "source": "suggestion",
        "source_suggestion_id": suggestion.id,
        "evidence_segment_ids_json": suggestion.evidence_segment_ids_json,
    }
    if model is Decision or model is ActionItem:
        values.update(title=suggestion.content, description=suggestion.content)
    row = model(**values)
    db.add(row)
    suggestion.status = "accepted"
    await db.flush()
    await emit(
        db,
        meeting.id,
        "suggestion.converted",
        "user",
        {"suggestion_id": suggestion.id, "kind": kind, "state_item_id": row.id},
    )
    await db.commit()
    return public_row(row, ("id", "meeting_id", "content", "source", "created_at"))


@router.post("/suggestions/{suggestion_id}/to-decision")
async def suggestion_to_decision(
    suggestion_id: str, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    return await convert_suggestion(suggestion_id, "decision", db)


@router.post("/suggestions/{suggestion_id}/to-action")
async def suggestion_to_action(
    suggestion_id: str, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    return await convert_suggestion(suggestion_id, "action_item", db)


@router.post("/suggestions/{suggestion_id}/to-question")
async def suggestion_to_question(
    suggestion_id: str, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    return await convert_suggestion(suggestion_id, "open_question", db)


@router.post("/suggestions/{suggestion_id}/to-risk")
async def suggestion_to_risk(
    suggestion_id: str, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    return await convert_suggestion(suggestion_id, "risk", db)


@router.post("/suggestions/{suggestion_id}/speak")
async def speak_suggestion(
    suggestion_id: str,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    row = await db.get(Suggestion, suggestion_id)
    if not row:
        raise HTTPException(404, "Suggestion not found")
    if row.status == "ignored":
        raise HTTPException(409, "Ignored suggestions cannot be spoken")
    meeting = await require_meeting(db, row.meeting_id)
    tts_language = str(meeting.configuration_json.get("tts_language", "zh-TW"))
    tts_voice = str(meeting.configuration_json.get("tts_voice", ""))
    tts_rate = float(meeting.configuration_json.get("tts_rate", 1))
    tts_volume = float(meeting.configuration_json.get("tts_volume", 1))
    provider_id = meeting.configuration_json.get("tts_provider_id", "browser-tts")
    provider = await db.get(ModelProvider, provider_id)
    if not provider or not provider.enabled:
        raise HTTPException(409, "TTS is disabled")
    if provider.provider_type == "browser_speech_synthesis":
        body = json.dumps(
            {
                "adapter": "browser_speech_synthesis",
                "text": row.content,
                "language": tts_language,
                "voice": tts_voice,
                "rate": tts_rate,
                "volume": tts_volume,
            },
            ensure_ascii=False,
        )
        return Response(body, media_type="application/json")
    if provider.provider_type != "openai_compatible_tts" or not provider.base_url:
        raise HTTPException(422, "Configured TTS provider cannot synthesize speech")
    import httpx

    headers = {"Content-Type": "application/json"}
    if settings.tts_worker_url and str(provider.base_url).startswith(
        settings.tts_worker_url.rstrip("/")
    ):
        headers["X-Worker-Token"] = settings.worker_token()
    if provider.secret_ref and os.environ.get(provider.secret_ref):
        headers["Authorization"] = f"Bearer {os.environ[provider.secret_ref]}"
    tts_started = perf_counter()
    async with httpx.AsyncClient(timeout=provider.timeout_seconds) as client:
        response = await client.post(
            str(provider.base_url).rstrip("/") + "/audio/speech",
            headers=headers,
            json={
                "model": provider.model,
                "input": row.content,
                "voice": tts_voice or provider.extra_json.get("voice", "zh"),
                "language": tts_language,
                "speed": tts_rate,
                "response_format": provider.extra_json.get("response_format", "wav"),
            },
        )
    if response.status_code >= 400:
        raise HTTPException(502, f"TTS endpoint returned HTTP {response.status_code}")
    await emit(
        db,
        row.meeting_id,
        "tts.completed",
        "tts-adapter",
        {
            "suggestion_id": row.id,
            "provider_id": provider.id,
            "latency_ms": round((perf_counter() - tts_started) * 1000, 2),
        },
    )
    await db.commit()
    return Response(response.content, media_type=response.headers.get("content-type", "audio/mpeg"))


@router.post("/meetings/{meeting_id}/state-items")
async def add_state_item(
    meeting_id: str, payload: StateItemCreate, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    await require_meeting(db, meeting_id)
    model: Any = {
        "decision": Decision,
        "open_question": OpenQuestion,
        "risk": Risk,
        "action_item": ActionItem,
    }.get(payload.kind)
    if payload.kind == "parking_lot":
        meeting = await require_meeting(db, meeting_id)
        config = dict(meeting.configuration_json)
        state = dict(config.get("state", {}))
        state["parking_lot"] = list(dict.fromkeys([*state.get("parking_lot", []), payload.content]))
        config["state"] = state
        meeting.configuration_json = config
        await emit(
            db,
            meeting_id,
            "state.updated",
            "user",
            {"kind": payload.kind, "content": payload.content},
        )
        await db.commit()
        return {"kind": payload.kind, "content": payload.content}
    assert model is not None
    existing = await db.scalar(
        select(model).where(
            model.meeting_id == meeting_id, func.lower(model.content) == payload.content.lower()
        )
    )
    if existing:
        return public_row(existing, ("id", "content", "source", "created_at"))
    values: dict[str, Any] = {
        "meeting_id": meeting_id,
        "project_id": (await require_meeting(db, meeting_id)).project_id,
        "content": payload.content,
        "source": "user",
    }
    if model is Decision or model is ActionItem:
        values.update(title=payload.content, description=payload.content)
    if model is ActionItem:
        values["owner"] = payload.owner
    row = model(**values)
    db.add(row)
    await db.flush()
    await emit(db, meeting_id, "state.updated", "user", {"kind": payload.kind, "id": row.id})
    await db.commit()
    return public_row(row, ("id", "content", "source", "created_at"))


def transcript_export_text(row: TranscriptSegment, language: str) -> str:
    if language != "original" and row.translated_text and row.translated_language == language:
        return row.translated_text
    return row.text


def render_vtt(rows: list[TranscriptSegment], language: str = "original") -> str:
    def stamp(ms: int) -> str:
        hours, rem = divmod(ms, 3_600_000)
        minutes, rem = divmod(rem, 60_000)
        seconds, millis = divmod(rem, 1000)
        return f"{hours:02}:{minutes:02}:{seconds:02}.{millis:03}"

    return "WEBVTT\n\n" + "\n\n".join(
        f"{row.sequence}\n{stamp(row.start_ms)} --> {stamp(row.end_ms)}\n"
        f"{transcript_export_text(row, language)}"
        for row in rows
    )


def render_srt(rows: list[TranscriptSegment], language: str = "original") -> str:
    def stamp(ms: int) -> str:
        hours, rem = divmod(ms, 3_600_000)
        minutes, rem = divmod(rem, 60_000)
        seconds, millis = divmod(rem, 1000)
        return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"

    return "\n\n".join(
        f"{index}\n{stamp(row.start_ms)} --> {stamp(row.end_ms)}\n"
        f"{transcript_export_text(row, language)}"
        for index, row in enumerate(rows, 1)
    )


async def export_data(
    meeting_id: str, db: AsyncSession
) -> tuple[Meeting, list[TranscriptSegment], list[Suggestion]]:
    meeting = await require_meeting(db, meeting_id)
    rows = list(
        (
            await db.scalars(
                select(TranscriptSegment)
                .where(TranscriptSegment.meeting_id == meeting_id)
                .order_by(TranscriptSegment.sequence)
            )
        ).all()
    )
    suggestions = list(
        (await db.scalars(select(Suggestion).where(Suggestion.meeting_id == meeting_id))).all()
    )
    return meeting, rows, suggestions


@router.post("/meetings/{meeting_id}/export/vtt")
async def export_vtt(meeting_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    meeting, rows, _ = await export_data(meeting_id, db)
    language = str(meeting.configuration_json.get("export_language", "original"))
    return Response(
        render_vtt(rows, language),
        media_type="text/vtt",
        headers={"Content-Disposition": f'attachment; filename="{meeting_id}.vtt"'},
    )


@router.post("/meetings/{meeting_id}/export/srt")
async def export_srt(meeting_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    meeting, rows, _ = await export_data(meeting_id, db)
    language = str(meeting.configuration_json.get("export_language", "original"))
    return Response(
        render_srt(rows, language),
        media_type="application/x-subrip",
        headers={"Content-Disposition": f'attachment; filename="{meeting_id}.srt"'},
    )


@router.post("/meetings/{meeting_id}/export/pdf")
async def export_pdf(meeting_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfgen import canvas

    meeting, rows, suggestions = await export_data(meeting_id, db)
    output = io.BytesIO()
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    document = canvas.Canvas(output)
    document.setTitle(meeting.title)
    document.setFont("STSong-Light", 16)
    document.drawString(48, 800, meeting.title)
    document.setFont("STSong-Light", 10)
    language = str(meeting.configuration_json.get("export_language", "original"))
    lines = [
        f"Goal: {meeting.goal}",
        "",
        "Transcript",
        *[
            f"{row.start_ms / 1000:.1f}s  {transcript_export_text(row, language)}"
            for row in rows
        ],
        "",
        "Suggestions",
        *[f"{row.category}: {row.content} ({row.status})" for row in suggestions],
    ]
    y = 776
    for line in lines:
        for offset in range(0, max(1, len(line)), 80):
            if y < 48:
                document.showPage()
                document.setFont("STSong-Light", 10)
                y = 800
            document.drawString(48, y, line[offset : offset + 80])
            y -= 15
    document.save()
    return Response(
        output.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{meeting_id}.pdf"'},
    )


@router.get("/meetings/{meeting_id}/summary")
async def meeting_summary(meeting_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    detail = await get_meeting(meeting_id, db)
    state = detail.meeting.configuration_json.get("state", {})
    return {
        "meeting_id": meeting_id,
        "executive_summary": state.get("rolling_summary", ""),
        "technical_summary": state.get("technical_summary", ""),
        "decisions": detail.decisions,
        "open_questions": detail.open_questions,
        "risks": detail.risks,
        "action_items": detail.action_items,
        "next_steps": state.get("next_steps", []),
        "suggested_agenda": state.get("suggested_agenda", []),
    }


async def group_count(db: AsyncSession, column: Any, meeting_id: str) -> dict[str, int]:
    rows = await db.execute(
        select(column, func.count()).where(column.class_.meeting_id == meeting_id).group_by(column)
    )
    return {str(key): int(value) for key, value in rows.all()}


def ratio(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def as_utc(value: datetime) -> datetime:
    # SQLite hands back naive datetimes; PostgreSQL keeps the offset.
    return value if value.tzinfo else value.replace(tzinfo=UTC)


@router.get("/meetings/{meeting_id}/analytics")
async def meeting_analytics(meeting_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Deterministic meeting metrics. Every number here is counted from the database, never
    generated by the reasoning engine."""
    meeting = await require_meeting(db, meeting_id)
    transcript_end = (
        await db.scalar(
            select(func.max(TranscriptSegment.end_ms)).where(
                TranscriptSegment.meeting_id == meeting_id
            )
        )
        or 0
    )
    if meeting.started_at and meeting.ended_at:
        duration_seconds = round((meeting.ended_at - meeting.started_at).total_seconds(), 1)
        duration_source = "meeting_timestamps"
    else:
        duration_seconds = round(transcript_end / 1000, 1)
        duration_source = "transcript_timeline"
    hours = duration_seconds / 3600

    segments, characters = (
        await db.execute(
            select(func.count(), func.coalesce(func.sum(func.length(TranscriptSegment.text)), 0))
            .select_from(TranscriptSegment)
            .where(TranscriptSegment.meeting_id == meeting_id)
        )
    ).one()
    speaker_rows = (
        await db.execute(
            select(
                TranscriptSegment.speaker_id,
                func.sum(TranscriptSegment.end_ms - TranscriptSegment.start_ms),
            )
            .where(
                TranscriptSegment.meeting_id == meeting_id,
                TranscriptSegment.speaker_id.is_not(None),
            )
            .group_by(TranscriptSegment.speaker_id)
        )
    ).all()
    labelled_ms = sum(int(value or 0) for _, value in speaker_rows)
    speakers = [
        {
            "speaker_id": speaker_id,
            "seconds": round(int(value or 0) / 1000, 1),
            "share": ratio(int(value or 0), labelled_ms),
        }
        for speaker_id, value in speaker_rows
    ]

    suggestions = await group_count(db, Suggestion.status, meeting_id)
    suggestion_total = sum(suggestions.values())
    decisions = await group_count(db, Decision.status, meeting_id)
    questions = await group_count(db, OpenQuestion.status, meeting_id)
    risks = await group_count(db, Risk.status, meeting_id)
    actions = list(
        (await db.scalars(select(ActionItem).where(ActionItem.meeting_id == meeting_id))).all()
    )
    runs = await group_count(db, CodexRun.status, meeting_id)
    run_total = sum(runs.values())
    run_latency = await db.scalar(
        select(func.avg(CodexRun.duration_ms)).where(
            CodexRun.meeting_id == meeting_id, CodexRun.duration_ms.is_not(None)
        )
    )

    now = datetime.now(UTC)
    closed = {"completed", "archived"}
    completed = [row for row in actions if row.status == "completed"]
    overdue = [
        row
        for row in actions
        if row.due_at and as_utc(row.due_at) < now and row.status not in closed
    ]
    completion_hours = [
        (as_utc(row.updated_at) - as_utc(row.created_at)).total_seconds() / 3600
        for row in completed
    ]
    unresolved = sum(count for status, count in questions.items() if status not in {"resolved"})

    return {
        "meeting_id": meeting_id,
        "duration_seconds": duration_seconds,
        "duration_source": duration_source,
        "transcript": {
            "segments": int(segments),
            "characters": int(characters),
            "speakers": speakers,
            # Speaker shares cover only manually labelled segments; there is no diarization.
            "speaker_labelled_ratio": ratio(labelled_ms, transcript_end),
        },
        "suggestions": {"total": suggestion_total, "by_status": suggestions},
        "suggestion_rates": {
            status: ratio(suggestions.get(status, 0), suggestion_total)
            for status in ("accepted", "edited", "converted", "ignored")
        },
        "decisions": {"total": sum(decisions.values()), "by_status": decisions},
        "open_questions": {"total": sum(questions.values()), "by_status": questions},
        "risks": {"total": sum(risks.values()), "by_status": risks},
        "actions": {
            "total": len(actions),
            "with_owner": sum(1 for row in actions if row.owner),
            "with_due_date": sum(1 for row in actions if row.due_at),
            "completed": len(completed),
            "overdue": len(overdue),
            "average_completion_hours": round(sum(completion_hours) / len(completion_hours), 1)
            if completion_hours
            else None,
        },
        "engine_runs": {
            "total": run_total,
            "by_status": runs,
            "average_duration_ms": round(float(run_latency), 1) if run_latency else None,
            "failure_rate": ratio(runs.get("failed", 0), run_total),
            "timeout_rate": ratio(runs.get("timed_out", 0), run_total),
        },
        "effectiveness": {
            "decisions_per_hour": round(sum(decisions.values()) / hours, 2) if hours else None,
            "actions_with_owner_ratio": ratio(
                sum(1 for row in actions if row.owner), len(actions)
            ),
            "actions_with_due_date_ratio": ratio(
                sum(1 for row in actions if row.due_at), len(actions)
            ),
            "unresolved_question_ratio": ratio(unresolved, sum(questions.values())),
        },
    }


@router.post("/meetings/{meeting_id}/export/json")
async def export_json(meeting_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    meeting, rows, suggestions = await export_data(meeting_id, db)
    data = {
        "meeting": MeetingRead.model_validate(meeting).model_dump(mode="json"),
        "transcript": [TranscriptRead.model_validate(row).model_dump(mode="json") for row in rows],
        "suggestions": [
            SuggestionRead.model_validate(row).model_dump(mode="json") for row in suggestions
        ],
    }
    return Response(
        json.dumps(data, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{meeting_id}.json"'},
    )


@router.post("/meetings/{meeting_id}/export/markdown")
async def export_markdown(meeting_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    meeting, rows, suggestions = await export_data(meeting_id, db)
    language = str(meeting.configuration_json.get("export_language", "original"))
    body = (
        f"# {meeting.title}\n\n**Goal:** {meeting.goal}\n\n## Transcript\n\n"
        + "\n\n".join(
            f"- `{row.start_ms / 1000:.1f}s` {transcript_export_text(row, language)}"
            for row in rows
        )
        + "\n\n## Codex suggestions\n\n"
        + "\n".join(f"- **{row.category}**: {row.content} ({row.status})" for row in suggestions)
    )
    return Response(
        body,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{meeting_id}.md"'},
    )


@router.websocket("/meetings/{meeting_id}/events")
async def events_socket(
    websocket: WebSocket, meeting_id: str, settings: Settings = Depends(get_settings)
) -> None:
    if not websocket_origin_allowed(
        websocket.headers.get("origin"), websocket.headers.get("host"), settings.allowed_origins
    ):
        await websocket.close(code=1008)
        return
    if remote_auth_applies(websocket.url.hostname, settings):
        async with SessionLocal() as db:
            if not await websocket_identity(websocket, db):
                await websocket.close(code=1008)
                return
    await hub.connect(meeting_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(meeting_id, websocket)


@router.websocket("/meetings/{meeting_id}/audio")
async def audio_socket(
    websocket: WebSocket, meeting_id: str, settings: Settings = Depends(get_settings)
) -> None:
    if not websocket_origin_allowed(
        websocket.headers.get("origin"), websocket.headers.get("host"), settings.allowed_origins
    ):
        await websocket.close(code=1008)
        return
    if remote_auth_applies(websocket.url.hostname, settings):
        async with SessionLocal() as db:
            if not await websocket_identity(websocket, db):
                await websocket.close(code=1008)
                return
    await websocket.accept()
    hub.audio_connected()
    service = create_stt_service(settings)
    buffer = bytearray()
    expected = 0
    # Resume the timeline after a reconnect: restarting at 0 rewinds timestamps,
    # duplicates transcript rows, and scrambles the transcript ordering.
    async with SessionLocal() as db:
        window_start = (
            await db.scalar(
                select(func.max(TranscriptSegment.end_ms)).where(
                    TranscriptSegment.meeting_id == meeting_id
                )
            )
            or 0
        )
    try:
        while True:
            frame = await websocket.receive_bytes()
            if len(frame) < 8 or len(frame) > settings.max_audio_frame_bytes:
                await websocket.close(code=1009)
                return
            sequence = int.from_bytes(frame[:8], "little")
            async with SessionLocal() as db:
                meeting = await db.get(Meeting, meeting_id)
                if not meeting or meeting.status != "active":
                    await websocket.send_json({"type": "error", "detail": "Meeting is not active"})
                    continue
                if sequence != expected:
                    await emit(
                        db,
                        meeting_id,
                        "audio.chunk.dropped",
                        "audio-gateway",
                        {"expected": expected, "received": sequence},
                    )
                expected = sequence + 1
                audio = frame[8:]
                start_ms = window_start + len(buffer) // 32
                existing_chunk = await db.scalar(
                    select(AudioChunk).where(
                        AudioChunk.meeting_id == meeting_id, AudioChunk.sequence == sequence
                    )
                )
                if existing_chunk:
                    await websocket.send_json(
                        {"type": "audio.ack", "sequence": sequence, "duplicate": True}
                    )
                    continue
                audio_path = None
                if meeting.audio_saved:
                    directory = settings.runtime_dir / "meetings" / meeting_id / "audio"
                    directory.mkdir(parents=True, exist_ok=True)
                    path = (directory / f"{sequence:010d}.pcm").resolve()
                    await asyncio.to_thread(path.write_bytes, audio)
                    audio_path = str(path)
                db.add(
                    AudioChunk(
                        meeting_id=meeting_id,
                        sequence=sequence,
                        path=audio_path,
                        start_ms=start_ms,
                        end_ms=start_ms + len(audio) // 32,
                        checksum=hashlib.sha256(audio).hexdigest(),
                        status="stored" if audio_path else "buffered",
                    )
                )
                await emit(
                    db,
                    meeting_id,
                    "audio.chunk.received",
                    "audio-gateway",
                    {"sequence": sequence, "bytes": len(audio)},
                )
                await db.commit()
                await websocket.send_json({"type": "audio.ack", "sequence": sequence})
                buffer.extend(audio)
                if len(buffer) >= 64_000:  # 2s window: halves transcript latency
                    try:
                        config = meeting.configuration_json
                        stt_language = (
                            "auto"
                            if config.get("secondary_language", "none") != "none"
                            else meeting.language
                        )
                        stt_started = perf_counter()
                        audio_duration_ms = len(buffer) / 32
                        previous = (
                            await db.scalar(
                                select(TranscriptSegment.text)
                                .where(TranscriptSegment.meeting_id == meeting_id)
                                .order_by(desc(TranscriptSegment.sequence))
                                .limit(1)
                            )
                            or ""
                        )
                        # Anchor whisper on script + prior text: fixes cross-window amnesia
                        # and biases zh output to the meeting's script (zh-TW ≠ zh-CN).
                        script_hint = {
                            "zh-TW": "以下是繁體中文會議逐字稿。",
                            "zh-CN": "以下是简体中文会议记录。",
                        }.get(meeting.language, "")
                        results = await service.transcribe(
                            bytes(buffer),
                            window_start,
                            stt_language,
                            prompt=(script_hint + previous[-150:]) or None,
                        )
                        stt_latency_ms = round((perf_counter() - stt_started) * 1000, 2)
                        await emit(
                            db,
                            meeting_id,
                            "stt.completed",
                            "stt-worker",
                            {
                                "latency_ms": stt_latency_ms,
                                "audio_duration_ms": round(audio_duration_ms, 2),
                                "real_time_factor": round(
                                    stt_latency_ms / audio_duration_ms, 4
                                ),
                                "segments": len(results),
                            },
                        )
                        glossary = (
                            list(
                                (
                                    await db.scalars(
                                        select(ProjectGlossary).where(
                                            ProjectGlossary.project_id == meeting.project_id
                                        )
                                    )
                                ).all()
                            )
                            if meeting.project_id
                            else []
                        )
                        next_sequence = (
                            await db.scalar(
                                select(func.max(TranscriptSegment.sequence)).where(
                                    TranscriptSegment.meeting_id == meeting_id
                                )
                            )
                            or 0
                        ) + 1
                        added_characters = 0
                        for result in results:
                            text = normalize_transcript(
                                merge_overlap(previous, result.text), glossary
                            )
                            if not text:
                                continue
                            await emit(
                                db,
                                meeting_id,
                                "transcript.partial",
                                "stt-worker",
                                {
                                    "text": text,
                                    "start_ms": result.start_ms,
                                    "end_ms": result.end_ms,
                                },
                            )
                            row = TranscriptSegment(
                                meeting_id=meeting_id,
                                sequence=next_sequence,
                                start_ms=result.start_ms,
                                end_ms=result.end_ms,
                                text=text,
                                language=result.language
                                or (meeting.language if meeting.language != "auto" else "und"),
                                confidence=result.confidence,
                                is_final=True,
                            )
                            db.add(row)
                            await db.flush()
                            added_characters += len(text)
                            await emit(
                                db,
                                meeting_id,
                                "transcript.final",
                                "stt-worker",
                                {
                                    "segment": TranscriptRead.model_validate(row).model_dump(
                                        mode="json"
                                    )
                                },
                            )
                            next_sequence += 1
                            previous += text
                        state = dict(config.get("state") or {})
                        accumulated_characters = accumulate_new_characters(
                            state, added_characters
                        )
                        state["new_transcript_characters"] = accumulated_characters
                        config = {**config, "state": state}
                        meeting.configuration_json = config
                        await db.commit()
                        trigger = decide_trigger(
                            TriggerContext(
                                text=" ".join(item.text for item in results),
                                status=meeting.status,
                                automatic_enabled=bool(
                                    config.get("automatic_analysis_enabled", True)
                                ),
                                new_characters=accumulated_characters,
                                minimum_characters=int(
                                    config.get(
                                        "minimum_new_characters",
                                        settings.minimum_new_characters,
                                    )
                                ),
                                last_codex_at=(
                                    datetime.fromisoformat(state["last_codex_run_at"])
                                    if state.get("last_codex_run_at")
                                    else None
                                ),
                                codex_cooldown_seconds=int(
                                    config.get(
                                        "codex_cooldown_seconds",
                                        settings.codex_cooldown_seconds,
                                    )
                                ),
                                last_suggestion_at=(
                                    datetime.fromisoformat(state["last_suggestion_at"])
                                    if state.get("last_suggestion_at")
                                    else None
                                ),
                                suggestion_cooldown_seconds=int(
                                    config.get(
                                        "suggestion_cooldown_seconds",
                                        settings.suggestion_cooldown_seconds,
                                    )
                                ),
                            )
                        )
                        active_run = (
                            await db.scalar(
                                select(func.count())
                                .select_from(CodexRun)
                                .where(
                                    CodexRun.meeting_id == meeting_id,
                                    CodexRun.status.in_(["queued", "running", "validating"]),
                                )
                            )
                            if trigger.invoke
                            else 0
                        )
                        if trigger.invoke and not active_run:
                            state["new_transcript_characters"] = 0
                            state["last_codex_run_at"] = datetime.now(UTC).isoformat()
                            meeting.configuration_json = {**config, "state": state}
                            all_transcripts = list(
                                (
                                    await db.scalars(
                                        select(TranscriptSegment)
                                        .where(TranscriptSegment.meeting_id == meeting_id)
                                        .order_by(desc(TranscriptSegment.sequence))
                                        .limit(100)
                                    )
                                ).all()
                            )[::-1]
                            prior_suggestions = list(
                                (
                                    await db.scalars(
                                        select(Suggestion)
                                        .where(Suggestion.meeting_id == meeting_id)
                                        .order_by(desc(Suggestion.created_at))
                                        .limit(20)
                                    )
                                ).all()
                            )
                            memory, glossary, knowledge = await get_project_context(db, meeting)
                            request = build_request(
                                meeting,
                                all_transcripts,
                                prior_suggestions,
                                "periodic_analysis",
                                None,
                                memory,
                                glossary,
                                knowledge,
                            )
                            engine = config.get("analysis_engine") or settings.analysis_engine
                            claude = engine == "claude"
                            run = CodexRun(
                                meeting_id=meeting_id,
                                job_type="periodic_analysis",
                                trigger=trigger.trigger or "periodic_analysis",
                                status="queued",
                                profile=None if claude else (config.get("codex_profile") or settings.codex_profile),
                                model=settings.claude_model if claude else settings.codex_model,
                                provider="claude_code" if claude else "codex_cli",
                                request_json=request,
                            )
                            db.add(run)
                            await db.flush()
                            await emit(
                                db,
                                meeting_id,
                                "trigger.detected",
                                "trigger-engine",
                                {"trigger": trigger.trigger},
                            )
                            await emit(
                                db, meeting_id, "codex.queued", "trigger-engine", {"run_id": run.id}
                            )
                            await db.commit()
                            manager.enqueue(run.id, meeting_id, settings, SessionLocal)
                    except Exception as exc:
                        await emit(
                            db,
                            meeting_id,
                            "system.warning",
                            "stt-worker",
                            {"message": f"STT unavailable: {type(exc).__name__}"},
                        )
                        await db.commit()
                    # Keep a 0.5s tail so consecutive windows overlap: words are no longer
                    # cut at window edges; merge_overlap strips the re-transcribed prefix.
                    advance = max(len(buffer) - 16_000, 0)
                    window_start += advance // 32
                    del buffer[:advance]
    except WebSocketDisconnect:
        if len(buffer) > 16_000:  # audio beyond the retained overlap tail: flush the last words
            try:
                config = meeting.configuration_json
                stt_language = (
                    "auto"
                    if config.get("secondary_language", "none") != "none"
                    else meeting.language
                )
                results = await service.transcribe(bytes(buffer), window_start, stt_language)
                glossary = (
                    list(
                        (
                            await db.scalars(
                                select(ProjectGlossary).where(
                                    ProjectGlossary.project_id == meeting.project_id
                                )
                            )
                        ).all()
                    )
                    if meeting.project_id
                    else []
                )
                previous = (
                    await db.scalar(
                        select(TranscriptSegment.text)
                        .where(TranscriptSegment.meeting_id == meeting_id)
                        .order_by(desc(TranscriptSegment.sequence))
                        .limit(1)
                    )
                    or ""
                )
                next_sequence = (
                    await db.scalar(
                        select(func.max(TranscriptSegment.sequence)).where(
                            TranscriptSegment.meeting_id == meeting_id
                        )
                    )
                    or 0
                ) + 1
                for result in results:
                    text = normalize_transcript(merge_overlap(previous, result.text), glossary)
                    if not text:
                        continue
                    row = TranscriptSegment(
                        meeting_id=meeting_id,
                        sequence=next_sequence,
                        start_ms=result.start_ms,
                        end_ms=result.end_ms,
                        text=text,
                        language=result.language
                        or (meeting.language if meeting.language != "auto" else "und"),
                        confidence=result.confidence,
                        is_final=True,
                    )
                    db.add(row)
                    await db.flush()
                    await emit(
                        db,
                        meeting_id,
                        "transcript.final",
                        "stt-worker",
                        {"segment": TranscriptRead.model_validate(row).model_dump(mode="json")},
                    )
                    next_sequence += 1
                    previous += text
                await db.commit()
            except Exception:  # noqa: BLE001 — flush is best-effort on disconnect
                pass
        return
    finally:
        hub.audio_disconnected()
