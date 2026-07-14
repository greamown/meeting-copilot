import hashlib
import json
import os
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, WebSocket, WebSocketDisconnect
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import allowlisted_path
from app.db.base import ActionItem, AudioChunk, CodexRun, Decision, Meeting, ModelProvider, OpenQuestion, Participant, Risk, Suggestion, TranscriptSegment
from app.db.session import SessionLocal, get_db
from app.schemas.meeting import AskRequest, CodexRunResponse, CommandResponse, MeetingCreate, MeetingDetail, MeetingRead, StateItemCreate, SuggestionEdit, SuggestionRead, TranscriptEdit, TranscriptRead
from app.services.codex import build_request, manager
from app.services.events import emit, hub
from app.services.stt import FasterWhisperService
from app.services.trigger import TriggerContext, decide_trigger, merge_overlap

router = APIRouter()


async def require_meeting(db: AsyncSession, meeting_id: str) -> Meeting:
    row = await db.get(Meeting, meeting_id)
    if not row: raise HTTPException(404, "Meeting not found")
    return row


def public_row(row: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: getattr(row, field) for field in fields}


@router.post("/meetings", response_model=MeetingRead, status_code=201)
async def create_meeting(payload: MeetingCreate, db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)) -> Meeting:
    repository_path = None
    if payload.repository_context_enabled:
        repository_path = str(allowlisted_path(payload.repository_path or "", settings.repository_roots))
    config = payload.model_dump(mode="json", exclude={"title", "goal", "language", "participants", "repository_context_enabled", "repository_path", "save_audio"})
    config["state"] = {"current_topic": "", "decisions": [], "open_questions": [], "risks": [], "action_items": [], "parking_lot": [], "last_codex_run_at": None, "last_suggestion_at": None, "new_transcript_characters": 0, "version": 1}
    row = Meeting(title=payload.title, goal=payload.goal, language=payload.language, configuration_json=config, audio_saved=payload.save_audio, repository_context_enabled=payload.repository_context_enabled, repository_path=repository_path)
    db.add(row); await db.flush()
    for index, name in enumerate(payload.participants): db.add(Participant(meeting_id=row.id, display_name=name, speaker_label=f"speaker-{index + 1}"))
    await emit(db, row.id, "meeting.created", "meeting-api", {"title": row.title}); await db.commit(); await db.refresh(row); return row


@router.get("/meetings", response_model=list[MeetingRead])
async def list_meetings(status: str | None = None, title: str | None = None, db: AsyncSession = Depends(get_db)) -> list[Meeting]:
    query = select(Meeting).order_by(desc(Meeting.created_at))
    if status: query = query.where(Meeting.status == status)
    if title: query = query.where(Meeting.title.ilike(f"%{title}%"))
    return list((await db.scalars(query)).all())


@router.get("/meetings/{meeting_id}", response_model=MeetingDetail)
async def get_meeting(meeting_id: str, db: AsyncSession = Depends(get_db)) -> MeetingDetail:
    meeting = await require_meeting(db, meeting_id)
    transcripts = list((await db.scalars(select(TranscriptSegment).where(TranscriptSegment.meeting_id == meeting_id).order_by(TranscriptSegment.sequence))).all())
    suggestions = list((await db.scalars(select(Suggestion).where(Suggestion.meeting_id == meeting_id).order_by(desc(Suggestion.created_at)))).all())
    decisions = list((await db.scalars(select(Decision).where(Decision.meeting_id == meeting_id))).all())
    questions = list((await db.scalars(select(OpenQuestion).where(OpenQuestion.meeting_id == meeting_id))).all())
    risks = list((await db.scalars(select(Risk).where(Risk.meeting_id == meeting_id))).all())
    actions = list((await db.scalars(select(ActionItem).where(ActionItem.meeting_id == meeting_id))).all())
    runs = list((await db.scalars(select(CodexRun).where(CodexRun.meeting_id == meeting_id).order_by(desc(CodexRun.created_at)))).all())
    item_fields = ("id", "content", "source", "source_suggestion_id", "created_at", "updated_at")
    run_fields = ("id", "job_type", "trigger", "status", "profile", "model", "provider", "sanitized_stderr", "started_at", "ended_at", "duration_ms", "created_at")
    return MeetingDetail(meeting=MeetingRead.model_validate(meeting), transcripts=[TranscriptRead.model_validate(row) for row in transcripts], suggestions=[SuggestionRead.model_validate(row) for row in suggestions], decisions=[public_row(row, item_fields) for row in decisions], open_questions=[public_row(row, item_fields + ("status",)) for row in questions], risks=[public_row(row, item_fields + ("status",)) for row in risks], action_items=[public_row(row, item_fields + ("owner", "due_at", "status")) for row in actions], codex_runs=[public_row(row, run_fields) for row in runs])


async def transition(db: AsyncSession, meeting_id: str, allowed: set[str], target: str, event_type: str) -> Meeting:
    row = await require_meeting(db, meeting_id)
    if row.status not in allowed: raise HTTPException(409, f"Cannot {target} meeting from {row.status}")
    row.status = target
    if target == "active" and not row.started_at: row.started_at = datetime.now(timezone.utc)
    if target == "ended": row.ended_at = datetime.now(timezone.utc)
    await emit(db, meeting_id, event_type, "meeting-api", {}); await db.commit(); await db.refresh(row); return row


@router.post("/meetings/{meeting_id}/start", response_model=CommandResponse)
async def start(meeting_id: str, db: AsyncSession = Depends(get_db)) -> CommandResponse: return CommandResponse(meeting=MeetingRead.model_validate(await transition(db, meeting_id, {"draft", "interrupted"}, "active", "meeting.started")))
@router.post("/meetings/{meeting_id}/pause", response_model=CommandResponse)
async def pause(meeting_id: str, db: AsyncSession = Depends(get_db)) -> CommandResponse: return CommandResponse(meeting=MeetingRead.model_validate(await transition(db, meeting_id, {"active"}, "paused", "meeting.paused")))
@router.post("/meetings/{meeting_id}/resume", response_model=CommandResponse)
async def resume(meeting_id: str, db: AsyncSession = Depends(get_db)) -> CommandResponse: return CommandResponse(meeting=MeetingRead.model_validate(await transition(db, meeting_id, {"paused"}, "active", "meeting.resumed")))
@router.post("/meetings/{meeting_id}/end", response_model=CommandResponse)
async def end(meeting_id: str, db: AsyncSession = Depends(get_db)) -> CommandResponse: return CommandResponse(meeting=MeetingRead.model_validate(await transition(db, meeting_id, {"active", "paused", "interrupted"}, "ended", "meeting.ended")))


@router.delete("/meetings/{meeting_id}", status_code=204)
async def delete_meeting(meeting_id: str, db: AsyncSession = Depends(get_db)) -> None:
    row = await require_meeting(db, meeting_id); await db.delete(row); await db.commit()


@router.delete("/meetings/{meeting_id}/audio", status_code=204)
async def delete_audio(meeting_id: str, db: AsyncSession = Depends(get_db)) -> None:
    meeting = await require_meeting(db, meeting_id)
    chunks = list((await db.scalars(select(AudioChunk).where(AudioChunk.meeting_id == meeting_id))).all())
    for chunk in chunks:
        if chunk.path:
            from pathlib import Path
            path = Path(chunk.path)
            if path.is_file(): path.unlink()
        await db.delete(chunk)
    meeting.audio_saved = False; await db.commit()


@router.patch("/transcripts/{segment_id}", response_model=TranscriptRead)
async def edit_transcript(segment_id: str, payload: TranscriptEdit, db: AsyncSession = Depends(get_db)) -> TranscriptSegment:
    row = await db.get(TranscriptSegment, segment_id)
    if not row: raise HTTPException(404, "Transcript segment not found")
    row.text, row.speaker_id, row.is_edited = payload.text, payload.speaker_id, True
    if payload.is_pinned is not None: row.is_pinned = payload.is_pinned
    await emit(db, row.meeting_id, "transcript.edited", "user", {"segment_id": row.id}); await db.commit(); await db.refresh(row); return row


async def request_codex(meeting_id: str, trigger: str, job_type: str, question: str | None, db: AsyncSession, settings: Settings) -> CodexRunResponse:
    meeting = await require_meeting(db, meeting_id)
    active = await db.scalar(select(func.count()).select_from(CodexRun).where(CodexRun.meeting_id == meeting_id, CodexRun.status.in_(["queued", "preparing_context", "running", "validating"])))
    if active: raise HTTPException(409, "A Codex job is already active for this meeting")
    transcripts = list((await db.scalars(select(TranscriptSegment).where(TranscriptSegment.meeting_id == meeting_id, TranscriptSegment.is_final.is_(True)).order_by(desc(TranscriptSegment.sequence)).limit(100))).all())[::-1]
    suggestions = list((await db.scalars(select(Suggestion).where(Suggestion.meeting_id == meeting_id).order_by(desc(Suggestion.created_at)).limit(20))).all())
    request = build_request(meeting, transcripts, suggestions, job_type, question)
    run = CodexRun(meeting_id=meeting_id, job_type=job_type, trigger=trigger, status="queued", profile=meeting.configuration_json.get("codex_profile") or settings.codex_profile, model=settings.codex_model, provider="codex_cli", request_json=request)
    db.add(run); await db.flush(); await emit(db, meeting_id, "codex.queued", "meeting-api", {"run_id": run.id, "trigger": trigger}); await db.commit()
    manager.enqueue(run.id, meeting_id, settings, SessionLocal)
    return CodexRunResponse(run_id=run.id, status="queued")


@router.post("/meetings/{meeting_id}/ask", response_model=CodexRunResponse)
async def ask(meeting_id: str, payload: AskRequest, db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)) -> CodexRunResponse: return await request_codex(meeting_id, "manual_ask", "manual_ask", payload.question, db, settings)
@router.post("/meetings/{meeting_id}/analyze", response_model=CodexRunResponse)
async def analyze(meeting_id: str, db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)) -> CodexRunResponse: return await request_codex(meeting_id, "manual_analysis", "periodic_analysis", None, db, settings)


@router.post("/codex-runs/{run_id}/cancel")
async def cancel_run(run_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    run = await db.get(CodexRun, run_id)
    if not run: raise HTTPException(404, "Codex run not found")
    cancelled = await manager.cancel(run_id)
    if run.status in ("queued", "preparing_context") or cancelled:
        run.status = "cancelled"; await emit(db, run.meeting_id, "codex.cancelled", "user", {"run_id": run.id}); await db.commit(); return {"cancelled": True}
    return {"cancelled": False, "status": run.status}


async def suggestion_action(suggestion_id: str, status: Literal["accepted", "ignored"], db: AsyncSession) -> Suggestion:
    row = await db.get(Suggestion, suggestion_id)
    if not row: raise HTTPException(404, "Suggestion not found")
    row.status = status; await emit(db, row.meeting_id, f"suggestion.{status}", "user", {"suggestion_id": row.id}); await db.commit(); await db.refresh(row); return row
@router.post("/suggestions/{suggestion_id}/accept", response_model=SuggestionRead)
async def accept_suggestion(suggestion_id: str, db: AsyncSession = Depends(get_db)) -> Suggestion: return await suggestion_action(suggestion_id, "accepted", db)
@router.post("/suggestions/{suggestion_id}/ignore", response_model=SuggestionRead)
async def ignore_suggestion(suggestion_id: str, db: AsyncSession = Depends(get_db)) -> Suggestion: return await suggestion_action(suggestion_id, "ignored", db)
@router.post("/suggestions/{suggestion_id}/edit", response_model=SuggestionRead)
async def edit_suggestion(suggestion_id: str, payload: SuggestionEdit, db: AsyncSession = Depends(get_db)) -> Suggestion:
    row = await db.get(Suggestion, suggestion_id)
    if not row: raise HTTPException(404, "Suggestion not found")
    row.content = payload.content; row.status = "edited"; await emit(db, row.meeting_id, "suggestion.edited", "user", {"suggestion_id": row.id}); await db.commit(); await db.refresh(row); return row
@router.post("/suggestions/{suggestion_id}/speak")
async def speak_suggestion(suggestion_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    row = await db.get(Suggestion, suggestion_id)
    if not row: raise HTTPException(404, "Suggestion not found")
    if row.status == "ignored": raise HTTPException(409, "Ignored suggestions cannot be spoken")
    meeting = await require_meeting(db, row.meeting_id)
    provider_id = meeting.configuration_json.get("tts_provider_id", "browser-tts")
    provider = await db.get(ModelProvider, provider_id)
    if not provider or provider.provider_type == "browser_speech_synthesis":
        body = json.dumps({"adapter": "browser_speech_synthesis", "text": row.content}, ensure_ascii=False)
        return Response(body, media_type="application/json")
    if provider.provider_type != "openai_compatible_tts" or not provider.base_url:
        raise HTTPException(422, "Configured TTS provider cannot synthesize speech")
    import httpx
    headers = {"Content-Type": "application/json"}
    if provider.secret_ref and os.environ.get(provider.secret_ref):
        headers["Authorization"] = f"Bearer {os.environ[provider.secret_ref]}"
    async with httpx.AsyncClient(timeout=provider.timeout_seconds) as client:
        response = await client.post(str(provider.base_url).rstrip("/") + "/audio/speech", headers=headers, json={"model": provider.model, "input": row.content, "voice": provider.extra_json.get("voice", "alloy"), "response_format": "mp3"})
    if response.status_code >= 400:
        raise HTTPException(502, f"TTS endpoint returned HTTP {response.status_code}")
    await emit(db, row.meeting_id, "tts.completed", "tts-adapter", {"suggestion_id": row.id, "provider_id": provider.id}); await db.commit()
    return Response(response.content, media_type=response.headers.get("content-type", "audio/mpeg"))


@router.post("/meetings/{meeting_id}/state-items")
async def add_state_item(meeting_id: str, payload: StateItemCreate, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    await require_meeting(db, meeting_id)
    model = {"decision": Decision, "open_question": OpenQuestion, "risk": Risk, "action_item": ActionItem}.get(payload.kind)
    if payload.kind == "parking_lot":
        meeting = await require_meeting(db, meeting_id); config = dict(meeting.configuration_json); state = dict(config.get("state", {})); state["parking_lot"] = list(dict.fromkeys([*state.get("parking_lot", []), payload.content])); config["state"] = state; meeting.configuration_json = config; await emit(db, meeting_id, "state.updated", "user", {"kind": payload.kind, "content": payload.content}); await db.commit(); return {"kind": payload.kind, "content": payload.content}
    assert model is not None
    existing = await db.scalar(select(model).where(model.meeting_id == meeting_id, func.lower(model.content) == payload.content.lower()))
    if existing: return public_row(existing, ("id", "content", "source", "created_at"))
    values = {"meeting_id": meeting_id, "content": payload.content, "source": "user"}
    if model is ActionItem: values["owner"] = payload.owner
    row = model(**values); db.add(row); await db.flush(); await emit(db, meeting_id, "state.updated", "user", {"kind": payload.kind, "id": row.id}); await db.commit(); return public_row(row, ("id", "content", "source", "created_at"))


def render_vtt(rows: list[TranscriptSegment]) -> str:
    def stamp(ms: int) -> str:
        hours, rem = divmod(ms, 3_600_000); minutes, rem = divmod(rem, 60_000); seconds, millis = divmod(rem, 1000); return f"{hours:02}:{minutes:02}:{seconds:02}.{millis:03}"
    return "WEBVTT\n\n" + "\n\n".join(f"{row.sequence}\n{stamp(row.start_ms)} --> {stamp(row.end_ms)}\n{row.text}" for row in rows)


async def export_data(meeting_id: str, db: AsyncSession) -> tuple[Meeting, list[TranscriptSegment], list[Suggestion]]:
    meeting = await require_meeting(db, meeting_id); rows = list((await db.scalars(select(TranscriptSegment).where(TranscriptSegment.meeting_id == meeting_id).order_by(TranscriptSegment.sequence))).all()); suggestions = list((await db.scalars(select(Suggestion).where(Suggestion.meeting_id == meeting_id))).all()); return meeting, rows, suggestions
@router.post("/meetings/{meeting_id}/export/vtt")
async def export_vtt(meeting_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    _, rows, _ = await export_data(meeting_id, db); return Response(render_vtt(rows), media_type="text/vtt", headers={"Content-Disposition": f'attachment; filename="{meeting_id}.vtt"'})
@router.post("/meetings/{meeting_id}/export/json")
async def export_json(meeting_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    meeting, rows, suggestions = await export_data(meeting_id, db); data = {"meeting": MeetingRead.model_validate(meeting).model_dump(mode="json"), "transcript": [TranscriptRead.model_validate(row).model_dump(mode="json") for row in rows], "suggestions": [SuggestionRead.model_validate(row).model_dump(mode="json") for row in suggestions]}; return Response(json.dumps(data, ensure_ascii=False, indent=2), media_type="application/json", headers={"Content-Disposition": f'attachment; filename="{meeting_id}.json"'})
@router.post("/meetings/{meeting_id}/export/markdown")
async def export_markdown(meeting_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    meeting, rows, suggestions = await export_data(meeting_id, db); body = f"# {meeting.title}\n\n**Goal:** {meeting.goal}\n\n## Transcript\n\n" + "\n\n".join(f"- `{row.start_ms / 1000:.1f}s` {row.text}" for row in rows) + "\n\n## Codex suggestions\n\n" + "\n".join(f"- **{row.category}**: {row.content} ({row.status})" for row in suggestions); return Response(body, media_type="text/markdown", headers={"Content-Disposition": f'attachment; filename="{meeting_id}.md"'})


@router.websocket("/meetings/{meeting_id}/events")
async def events_socket(websocket: WebSocket, meeting_id: str, settings: Settings = Depends(get_settings)) -> None:
    origin = websocket.headers.get("origin")
    if origin and origin not in settings.allowed_origins: await websocket.close(code=1008); return
    await hub.connect(meeting_id, websocket)
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect: hub.disconnect(meeting_id, websocket)


@router.websocket("/meetings/{meeting_id}/audio")
async def audio_socket(websocket: WebSocket, meeting_id: str, settings: Settings = Depends(get_settings)) -> None:
    origin = websocket.headers.get("origin")
    if origin and origin not in settings.allowed_origins: await websocket.close(code=1008); return
    await websocket.accept(); service = FasterWhisperService(settings.stt_model, settings.stt_device, settings.stt_compute_type, settings.stt_fallback_model); buffer = bytearray(); expected = 0; window_start = 0
    try:
        while True:
            frame = await websocket.receive_bytes()
            if len(frame) < 8 or len(frame) > settings.max_audio_frame_bytes: await websocket.close(code=1009); return
            sequence = int.from_bytes(frame[:8], "little")
            async with SessionLocal() as db:
                meeting = await db.get(Meeting, meeting_id)
                if not meeting or meeting.status != "active": await websocket.send_json({"type": "error", "detail": "Meeting is not active"}); continue
                if sequence != expected: await emit(db, meeting_id, "audio.chunk.dropped", "audio-gateway", {"expected": expected, "received": sequence})
                expected = sequence + 1; audio = frame[8:]; start_ms = window_start + len(buffer) // 32
                existing_chunk = await db.scalar(select(AudioChunk).where(AudioChunk.meeting_id == meeting_id, AudioChunk.sequence == sequence))
                if existing_chunk:
                    await websocket.send_json({"type": "audio.ack", "sequence": sequence, "duplicate": True}); continue
                audio_path = None
                if meeting.audio_saved:
                    directory = settings.runtime_dir / "meetings" / meeting_id / "audio"; directory.mkdir(parents=True, exist_ok=True)
                    path = (directory / f"{sequence:010d}.pcm").resolve(); await asyncio.to_thread(path.write_bytes, audio); audio_path = str(path)
                db.add(AudioChunk(meeting_id=meeting_id, sequence=sequence, path=audio_path, start_ms=start_ms, end_ms=start_ms + len(audio) // 32, checksum=hashlib.sha256(audio).hexdigest(), status="stored" if audio_path else "buffered")); await emit(db, meeting_id, "audio.chunk.received", "audio-gateway", {"sequence": sequence, "bytes": len(audio)}); await db.commit(); await websocket.send_json({"type": "audio.ack", "sequence": sequence}); buffer.extend(audio)
                if len(buffer) >= 128_000:
                    try:
                        results = await service.transcribe(bytes(buffer), window_start, meeting.language)
                        previous = await db.scalar(select(TranscriptSegment.text).where(TranscriptSegment.meeting_id == meeting_id).order_by(desc(TranscriptSegment.sequence)).limit(1)) or ""
                        next_sequence = (await db.scalar(select(func.max(TranscriptSegment.sequence)).where(TranscriptSegment.meeting_id == meeting_id)) or 0) + 1
                        for result in results:
                            text = merge_overlap(previous, result.text)
                            if not text: continue
                            await emit(db, meeting_id, "transcript.partial", "stt-worker", {"text": text, "start_ms": result.start_ms, "end_ms": result.end_ms})
                            row = TranscriptSegment(meeting_id=meeting_id, sequence=next_sequence, start_ms=result.start_ms, end_ms=result.end_ms, text=text, confidence=result.confidence, is_final=True); db.add(row); await db.flush(); await emit(db, meeting_id, "transcript.final", "stt-worker", {"segment": TranscriptRead.model_validate(row).model_dump(mode="json")}); next_sequence += 1; previous += text
                        await db.commit()
                        config = meeting.configuration_json
                        trigger = decide_trigger(TriggerContext(text=" ".join(item.text for item in results), status=meeting.status, automatic_enabled=bool(config.get("automatic_analysis_enabled", True)), new_characters=sum(len(item.text) for item in results), minimum_characters=int(config.get("minimum_new_characters", 300)), suggestion_cooldown_seconds=int(config.get("suggestion_cooldown_seconds", 180))))
                        active_run = await db.scalar(select(func.count()).select_from(CodexRun).where(CodexRun.meeting_id == meeting_id, CodexRun.status.in_(["queued", "running", "validating"])))
                        if trigger.invoke and not active_run:
                            all_transcripts = list((await db.scalars(select(TranscriptSegment).where(TranscriptSegment.meeting_id == meeting_id).order_by(desc(TranscriptSegment.sequence)).limit(100))).all())[::-1]
                            prior_suggestions = list((await db.scalars(select(Suggestion).where(Suggestion.meeting_id == meeting_id).order_by(desc(Suggestion.created_at)).limit(20))).all())
                            request = build_request(meeting, all_transcripts, prior_suggestions, "periodic_analysis", None)
                            run = CodexRun(meeting_id=meeting_id, job_type="periodic_analysis", trigger=trigger.trigger or "periodic_analysis", status="queued", profile=config.get("codex_profile") or settings.codex_profile, model=settings.codex_model, provider="codex_cli", request_json=request)
                            db.add(run); await db.flush(); await emit(db, meeting_id, "trigger.detected", "trigger-engine", {"trigger": trigger.trigger}); await emit(db, meeting_id, "codex.queued", "trigger-engine", {"run_id": run.id}); await db.commit(); manager.enqueue(run.id, meeting_id, settings, SessionLocal)
                    except Exception as exc:
                        await emit(db, meeting_id, "system.warning", "stt-worker", {"message": f"STT unavailable: {type(exc).__name__}"}); await db.commit()
                    window_start += len(buffer) // 32; buffer.clear()
    except WebSocketDisconnect: return
