import asyncio
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

import httpx
from pydantic import ValidationError
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import redact, scrub_mapping
from app.db.base import (
    ActionItem,
    CodexRun,
    Decision,
    KnowledgeDocument,
    Meeting,
    MeetingState,
    OpenQuestion,
    ProjectGlossary,
    ProjectMemory,
    Risk,
    Suggestion,
    TranscriptSegment,
)
from app.schemas.meeting import CodexOutput
from app.services.events import emit
from app.services.glossary import normalize_translation
from app.services.trigger import similar

AGENT_INSTRUCTIONS = """You are a meeting discussion assistant.
MUST:
- Use only the provided meeting context and explicitly enabled files.
- Do not claim facts not supported by the transcript or referenced files.
- Do not modify files. Do not access the network. Do not execute destructive commands.
- Return valid JSON conforming to the provided schema.
- Set should_suggest=false when there is no material new value.
- Avoid repeating recent suggestions. Keep suggestions concise and actionable.
- Distinguish facts, inferences, risks, and questions.
- Never replace original transcript text. When a translation target is configured, return
  translations in the dedicated translations array and follow glossary do-not-translate rules.
- Write suggestions and summaries in their independently requested output languages.
SHOULD:
- Detect contradictions and missing decisions.
- Surface operational, security, reliability, cost, and maintenance risks.
- Turn vague discussion into a concrete next question.
"""


def build_request(
    meeting: Meeting,
    transcripts: list[TranscriptSegment],
    suggestions: list[Suggestion],
    job_type: str,
    manual_question: str | None,
    project_memory: list[ProjectMemory] | None = None,
    glossary: list[ProjectGlossary] | None = None,
    knowledge: list[KnowledgeDocument] | None = None,
) -> dict[str, Any]:
    state = meeting.configuration_json.get("state", {})
    analysis_mode = meeting.configuration_json.get("analysis_language_mode", "original")
    recent_transcript: list[dict[str, Any]] = []
    characters = 0
    for row in reversed(transcripts):
        if recent_transcript and characters + len(row.text) > 12_000:
            break
        item = {
            "segment_id": row.id,
            "speaker_id": row.speaker_id,
            "start_ms": row.start_ms,
            "end_ms": row.end_ms,
            "language": row.language,
            "text": row.translated_text
            if analysis_mode == "translated" and row.translated_text
            else row.text,
            "confidence": row.confidence,
        }
        if analysis_mode == "both":
            item.update(
                original_text=row.text,
                translated_language=row.translated_language,
                translated_text=row.translated_text,
            )
        recent_transcript.append(item)
        characters += len(row.text)
    recent_transcript.reverse()
    return {
        "job_id": str(uuid4()),
        "meeting_id": meeting.id,
        "project_id": meeting.project_id,
        "job_type": job_type,
        "language": {
            "input": meeting.language,
            "secondary": meeting.configuration_json.get("secondary_language", "none"),
            "output": meeting.configuration_json.get("suggestion_language", "zh-TW"),
            "summary": meeting.configuration_json.get("summary_language", "zh-TW"),
            "translation": meeting.configuration_json.get("translation_language", "none"),
            "analysis_mode": meeting.configuration_json.get("analysis_language_mode", "original"),
        },
        "meeting": {
            "title": meeting.title,
            "goal": meeting.goal,
            "current_topic": state.get("current_topic", ""),
            "decisions": state.get("decisions", []),
            "open_questions": state.get("open_questions", []),
            "risks": state.get("risks", []),
            "action_items": state.get("action_items", []),
        },
        "project_memory": [
            {
                "id": row.id,
                "category": row.category,
                "title": row.title,
                "content": row.content,
                "confidence": row.confidence,
                "version": row.version,
            }
            for row in (project_memory or [])
        ],
        "glossary": [
            {
                "term": row.term,
                "language": row.language,
                "preferred_spelling": row.preferred_spelling,
                "translation": row.translation,
                "aliases": row.aliases_json,
                "do_not_translate": row.do_not_translate,
            }
            for row in (glossary or [])
        ],
        "knowledge_context": [
            {
                "id": row.id,
                "source_type": row.source_type,
                "title": row.title,
                "content": row.content[:4000],
                "language": row.language,
            }
            for row in (knowledge or [])
        ],
        "recent_transcript": recent_transcript,
        "recent_suggestions": [
            {"category": row.category, "suggestion": row.content} for row in suggestions
        ],
        "manual_question": manual_question,
        "review_roles": meeting.configuration_json.get("review_roles", []),
        "repository_context": {
            "enabled": meeting.repository_context_enabled,
            "path": meeting.repository_path if meeting.repository_context_enabled else None,
        },
    }


async def get_project_context(
    db: AsyncSession, meeting: Meeting
) -> tuple[list[ProjectMemory], list[ProjectGlossary], list[KnowledgeDocument]]:
    if not meeting.project_id:
        return [], [], []
    memory = list(
        (
            await db.scalars(
                select(ProjectMemory)
                .where(
                    ProjectMemory.project_id == meeting.project_id,
                    ProjectMemory.status == "active",
                )
                .order_by(desc(ProjectMemory.updated_at))
                .limit(40)
            )
        ).all()
    )
    glossary = list(
        (
            await db.scalars(
                select(ProjectGlossary)
                .where(ProjectGlossary.project_id == meeting.project_id)
                .order_by(ProjectGlossary.term)
                .limit(100)
            )
        ).all()
    )
    knowledge = list(
        (
            await db.scalars(
                select(KnowledgeDocument)
                .where(KnowledgeDocument.project_id == meeting.project_id)
                .order_by(desc(KnowledgeDocument.updated_at))
                .limit(20)
            )
        ).all()
    )
    return memory, glossary, knowledge


class CodexManager:
    """Serializes Codex per meeting and tracks cancellable subprocesses."""

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._tasks: set[asyncio.Task[None]] = set()
        self._tasks_by_run: dict[str, asyncio.Task[None]] = {}
        self._cancelled_runs: set[str] = set()

    def enqueue(
        self, run_id: str, meeting_id: str, settings: Settings, session_factory: Any
    ) -> None:
        task = asyncio.create_task(self._run(run_id, meeting_id, settings, session_factory))
        self._tasks.add(task)
        self._tasks_by_run[run_id] = task

        def discard(completed: asyncio.Task[None]) -> None:
            self._tasks.discard(completed)
            self._tasks_by_run.pop(run_id, None)
            self._cancelled_runs.discard(run_id)

        task.add_done_callback(discard)

    async def shutdown(self) -> None:
        """Stop active subprocesses and wait for all tracked jobs to finish."""
        for process in list(self._processes.values()):
            if process.returncode is None:
                try:
                    process.terminate()
                except ProcessLookupError:
                    pass
        tasks = list(self._tasks)
        if tasks:
            _, pending = await asyncio.wait(tasks, timeout=5)
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
        for process in list(self._processes.values()):
            if process.returncode is None:
                try:
                    await asyncio.wait_for(process.wait(), 5)
                except TimeoutError:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                    await process.wait()
        self._processes.clear()
        self._tasks.clear()
        self._tasks_by_run.clear()
        self._cancelled_runs.clear()

    async def _wait_for_run(self, run_id: str) -> None:
        task = self._tasks_by_run.get(run_id)
        if task and task is not asyncio.current_task():
            try:
                await asyncio.wait_for(asyncio.shield(task), 10)
            except (TimeoutError, asyncio.CancelledError):
                pass

    async def cancel(self, run_id: str, settings: Settings | None = None) -> bool:
        if settings and settings.codex_worker_url:
            token = settings.worker_token()
            if not token:
                return False
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.post(
                        f"{settings.codex_worker_url.rstrip('/')}/v1/jobs/{run_id}/cancel",
                        headers={"X-Worker-Token": token},
                    )
                cancelled = response.is_success and bool(response.json().get("cancelled"))
                if cancelled:
                    await self._wait_for_run(run_id)
                return cancelled
            except httpx.HTTPError:
                return False
        process = self._processes.get(run_id)
        if process and process.returncode is None:
            self._cancelled_runs.add(run_id)
            try:
                process.terminate()
            except ProcessLookupError:
                return True
            try:
                await asyncio.wait_for(process.wait(), 5)
            except TimeoutError:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                await process.wait()
            await self._wait_for_run(run_id)
            return True
        task = self._tasks_by_run.get(run_id)
        if task and not task.done():
            self._cancelled_runs.add(run_id)
            await self._wait_for_run(run_id)
            return True
        return False

    async def _run(
        self, run_id: str, meeting_id: str, settings: Settings, session_factory: Any
    ) -> None:
        async with self._locks[meeting_id], session_factory() as db:
            run = await db.get(CodexRun, run_id)
            if not run or run.status == "cancelled" or run_id in self._cancelled_runs:
                return
            await self._execute(db, run, settings)

    async def _execute(self, db: AsyncSession, run: CodexRun, settings: Settings) -> None:
        meeting = await db.get(Meeting, run.meeting_id)
        if not meeting:
            return
        runtime = settings.runtime_dir / "meetings" / meeting.id
        runs_dir = runtime / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        schema_path = Path(__file__).resolve().parents[3] / "schemas" / "codex-response.schema.json"
        output_path = runs_dir / f"{run.id}-response.json"
        request_path = runs_dir / f"{run.id}-request.json"
        runtime.joinpath("AGENTS.md").write_text(AGENT_INSTRUCTIONS)
        request_path.write_text(
            json.dumps(scrub_mapping(run.request_json), ensure_ascii=False, indent=2)
        )
        run.status, run.started_at = "running", datetime.now(UTC)
        await emit(db, meeting.id, "codex.started", "codex-worker", {"run_id": run.id})
        await db.commit()
        started = perf_counter()
        try:
            if run.id in self._cancelled_runs:
                return
            if settings.codex_worker_url:
                result = await self._remote_execute(run, settings)
            else:
                command = [
                    settings.codex_bin,
                    "exec",
                    "--sandbox",
                    "read-only",
                    "--ephemeral",
                    "--skip-git-repo-check",
                    "--output-schema",
                    str(schema_path),
                    "--output-last-message",
                    str(output_path),
                    "--color",
                    "never",
                    "-C",
                    str(runtime),
                ]
                if run.model:
                    command.extend(["--model", run.model])
                if run.profile:
                    command.extend(["--profile", run.profile])
                prompt = (
                    "Analyze the meeting request in this JSON and return only the required "
                    "structured result:\n" + json.dumps(run.request_json, ensure_ascii=False)
                )
                process = await asyncio.create_subprocess_exec(
                    *command, prompt, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                self._processes[run.id] = process
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), settings.codex_timeout_seconds
                )
                if run.status == "cancelled" or run.id in self._cancelled_runs:
                    return
                if process.returncode != 0:
                    raise RuntimeError(
                        redact(stderr.decode(errors="replace") or stdout.decode(errors="replace"))
                    )
                run.status = "validating"
                await db.commit()
                raw = (
                    output_path.read_text()
                    if output_path.exists()
                    else stdout.decode(errors="replace")
                )
                try:
                    result = CodexOutput.model_validate_json(raw)
                except ValidationError:
                    run.retry_count = 1
                    repair_path = runs_dir / f"{run.id}-repair.json"
                    repair_command = [
                        settings.codex_bin,
                        "exec",
                        "--sandbox",
                        "read-only",
                        "--ephemeral",
                        "--skip-git-repo-check",
                        "--output-schema",
                        str(schema_path),
                        "--output-last-message",
                        str(repair_path),
                        "--color",
                        "never",
                        "-C",
                        str(runtime),
                    ]
                    repair = await asyncio.create_subprocess_exec(
                        *repair_command,
                        "Repair the following invalid response. Return only JSON matching the "
                        "output schema, without adding claims:\n" + raw[:12000],
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    self._processes[run.id] = repair
                    repair_stdout, repair_stderr = await asyncio.wait_for(
                        repair.communicate(), min(60, settings.codex_timeout_seconds)
                    )
                    if repair.returncode != 0:
                        raise RuntimeError(redact(repair_stderr.decode(errors="replace"))) from None
                    result = CodexOutput.model_validate_json(
                        repair_path.read_text()
                        if repair_path.exists()
                        else repair_stdout.decode(errors="replace")
                    )
            valid_ids = {item["segment_id"] for item in run.request_json["recent_transcript"]}
            referenced_ids = {
                *result.evidence_segment_ids,
                *(item.segment_id for item in result.translations),
            }
            if not referenced_ids.issubset(valid_ids):
                raise ValueError("Codex cited transcript segments outside the request")
            run.response_json = result.model_dump(mode="json")
            await apply_state_patch(db, meeting, result)
            if result.should_suggest and result.suggestion:
                recent = list(
                    (
                        await db.scalars(
                            select(Suggestion)
                            .where(Suggestion.meeting_id == meeting.id)
                            .order_by(desc(Suggestion.created_at))
                            .limit(20)
                        )
                    ).all()
                )
                if not any(similar(result.suggestion, item.content) for item in recent):
                    suggestion = Suggestion(
                        meeting_id=meeting.id,
                        codex_run_id=run.id,
                        category=result.category,
                        content=result.suggestion,
                        reason=result.reason,
                        follow_up_question=result.follow_up_question,
                        confidence=result.confidence,
                        trigger=run.trigger,
                        evidence_segment_ids_json=result.evidence_segment_ids,
                    )
                    db.add(suggestion)
                    await db.flush()
                    await emit(
                        db,
                        meeting.id,
                        "suggestion.created",
                        "codex-worker",
                        {
                            "suggestion_id": suggestion.id,
                            "category": suggestion.category,
                            "content": suggestion.content,
                        },
                    )
                else:
                    await emit(
                        db,
                        meeting.id,
                        "suggestion.duplicate_suppressed",
                        "codex-worker",
                        {"run_id": run.id, "category": result.category},
                    )
            run.status = "completed"
            await emit(
                db,
                meeting.id,
                "codex.completed",
                "codex-worker",
                {"run_id": run.id, "should_suggest": result.should_suggest},
            )
        except TimeoutError:
            timed_out_process = self._processes.get(run.id)
            if timed_out_process and timed_out_process.returncode is None:
                try:
                    timed_out_process.kill()
                except ProcessLookupError:
                    pass
            run.status, run.sanitized_stderr = "timed_out", "Codex execution timed out"
            await emit(db, meeting.id, "codex.timed_out", "codex-worker", {"run_id": run.id})
        except (RuntimeError, ValueError, ValidationError, OSError) as exc:
            run.status, run.sanitized_stderr = "failed", redact(str(exc))
            await emit(
                db,
                meeting.id,
                "codex.failed",
                "codex-worker",
                {"run_id": run.id, "error": run.sanitized_stderr},
            )
        finally:
            self._processes.pop(run.id, None)
            run.ended_at = datetime.now(UTC)
            run.duration_ms = round((perf_counter() - started) * 1000)
            await db.commit()

    async def _remote_execute(self, run: CodexRun, settings: Settings) -> CodexOutput:
        worker_url = settings.codex_worker_url
        if not worker_url:
            raise RuntimeError("Codex worker URL is not configured")
        token = settings.worker_token()
        if not token:
            raise RuntimeError("Worker token is not configured")
        payload = {
            "run_id": run.id,
            "meeting_id": run.meeting_id,
            "request": run.request_json,
            "profile": run.profile,
            "model": run.model,
            "timeout_seconds": settings.codex_timeout_seconds,
        }
        response: httpx.Response | None = None
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=settings.codex_timeout_seconds + 15) as client:
                    response = await client.post(
                        f"{worker_url.rstrip('/')}/v1/execute",
                        headers={"X-Worker-Token": token, "X-Request-ID": run.id},
                        json=payload,
                    )
                if response.status_code < 500 or response.status_code == 504:
                    break
            except httpx.TimeoutException as exc:
                raise TimeoutError from exc
            except httpx.TransportError:
                if attempt == 1:
                    raise RuntimeError("Codex worker transport failed") from None
            run.retry_count = attempt + 1
            await asyncio.sleep(0.5 * (attempt + 1))
        if response is None:
            raise RuntimeError("Codex worker did not return a response")
        if response.status_code == 504:
            raise TimeoutError
        if not response.is_success:
            raise RuntimeError(redact(response.text))
        body = response.json()
        run.retry_count = int(body.get("retry_count", 0))
        run.status = "validating"
        return CodexOutput.model_validate(body["result"])


manager = CodexManager()


async def apply_state_patch(db: AsyncSession, meeting: Meeting, result: CodexOutput) -> None:
    """Apply allowlisted generated additions without replacing user-owned items."""
    patch = result.state_patch
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
    for translation in result.translations:
        segment = await db.get(TranscriptSegment, translation.segment_id)
        if segment and segment.meeting_id == meeting.id:
            segment.translated_language = translation.language
            segment.translated_text = normalize_translation(translation.text, glossary)
    config = dict(meeting.configuration_json)
    state = dict(config.get("state", {}))
    if patch.current_topic and state.get("current_topic_source") != "user":
        state["current_topic"] = patch.current_topic
        state["current_topic_source"] = "codex"
    model_groups: list[tuple[Any, list[str], str]] = [
        (Decision, patch.add_decisions, "decisions"),
        (OpenQuestion, patch.add_open_questions, "open_questions"),
        (Risk, patch.add_risks, "risks"),
        (ActionItem, patch.add_action_items, "action_items"),
    ]
    for model, additions, state_key in model_groups:
        existing_rows = list(
            (await db.scalars(select(model).where(model.meeting_id == meeting.id))).all()
        )
        existing = [row.content for row in existing_rows]
        accepted: list[str] = []
        for content in additions:
            if content and not any(similar(content, old) for old in existing):
                values: dict[str, Any] = {
                    "meeting_id": meeting.id,
                    "project_id": meeting.project_id,
                    "content": content,
                    "source": "codex",
                }
                if model is Decision or model is ActionItem:
                    values.update(title=content, description=content)
                db.add(model(**values))
                existing.append(content)
                accepted.append(content)
        state[state_key] = list(dict.fromkeys([*state.get(state_key, []), *accepted]))
    state["parking_lot"] = list(
        dict.fromkeys([*state.get("parking_lot", []), *patch.add_parking_lot])
    )
    if result.summary_patch.current_topic and state.get("current_topic_source") != "user":
        state["current_topic"] = result.summary_patch.current_topic
    if result.summary_patch.discussion_summary:
        state["rolling_summary"] = result.summary_patch.discussion_summary
    state["next_steps"] = list(dict.fromkeys([*state.get("next_steps", []), *result.next_steps]))
    state["suggested_agenda"] = list(
        dict.fromkeys([*state.get("suggested_agenda", []), *result.suggested_agenda])
    )
    if meeting.project_id:
        existing_memory = list(
            (
                await db.scalars(
                    select(ProjectMemory).where(ProjectMemory.project_id == meeting.project_id)
                )
            ).all()
        )
        for content in patch.add_project_memory:
            if content and not any(similar(content, row.content) for row in existing_memory):
                memory = ProjectMemory(
                    project_id=meeting.project_id,
                    category="lessons_learned",
                    title=content[:300],
                    content=content,
                    source_meeting_id=meeting.id,
                    confidence=result.confidence,
                    status="active",
                )
                db.add(memory)
                existing_memory.append(memory)
    state["version"] = int(state.get("version", 0)) + 1
    state["last_codex_run_at"] = datetime.now(UTC).isoformat()
    config["state"] = state
    meeting.configuration_json = config
    db.add(
        MeetingState(
            meeting_id=meeting.id,
            version=state["version"],
            current_topic=state.get("current_topic", ""),
            state_json=state,
            source="codex",
        )
    )
    await emit(db, meeting.id, "state.updated", "codex-worker", {"version": state["version"]})
