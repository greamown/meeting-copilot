import asyncio
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import allowlisted_path, redact, scrub_mapping
from app.db.base import ActionItem, CodexRun, Decision, Meeting, MeetingState, OpenQuestion, Risk, Suggestion, TranscriptSegment
from app.schemas.meeting import CodexOutput
from app.services.events import emit
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
SHOULD:
- Detect contradictions and missing decisions.
- Surface operational, security, reliability, cost, and maintenance risks.
- Turn vague discussion into a concrete next question.
"""


def build_request(meeting: Meeting, transcripts: list[TranscriptSegment], suggestions: list[Suggestion], job_type: str, manual_question: str | None) -> dict[str, Any]:
    state = meeting.configuration_json.get("state", {})
    return {
        "job_id": str(uuid4()), "meeting_id": meeting.id, "job_type": job_type,
        "meeting": {"title": meeting.title, "goal": meeting.goal, "current_topic": state.get("current_topic", ""), "decisions": state.get("decisions", []), "open_questions": state.get("open_questions", []), "risks": state.get("risks", []), "action_items": state.get("action_items", [])},
        "recent_transcript": [{"segment_id": row.id, "speaker_id": row.speaker_id, "start_ms": row.start_ms, "end_ms": row.end_ms, "text": row.text, "confidence": row.confidence} for row in transcripts],
        "recent_suggestions": [{"category": row.category, "suggestion": row.content} for row in suggestions],
        "manual_question": manual_question,
        "repository_context": {"enabled": meeting.repository_context_enabled, "path": meeting.repository_path if meeting.repository_context_enabled else None},
    }


class CodexManager:
    """Serializes Codex per meeting and tracks cancellable subprocesses."""

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._tasks: set[asyncio.Task[None]] = set()

    def enqueue(self, run_id: str, meeting_id: str, settings: Settings, session_factory: Any) -> None:
        task = asyncio.create_task(self._run(run_id, meeting_id, settings, session_factory))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def cancel(self, run_id: str) -> bool:
        process = self._processes.get(run_id)
        if process and process.returncode is None:
            try:
                process.terminate()
            except ProcessLookupError:
                return True
            try:
                await asyncio.wait_for(process.wait(), 5)
            except asyncio.TimeoutError:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
            return True
        return False

    async def _run(self, run_id: str, meeting_id: str, settings: Settings, session_factory: Any) -> None:
        async with self._locks[meeting_id], session_factory() as db:
            run = await db.get(CodexRun, run_id)
            if not run or run.status == "cancelled":
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
        request_path.write_text(json.dumps(scrub_mapping(run.request_json), ensure_ascii=False, indent=2))
        run.status, run.started_at = "running", datetime.now(timezone.utc)
        await emit(db, meeting.id, "codex.started", "codex-worker", {"run_id": run.id})
        await db.commit()
        command = [settings.codex_bin, "exec", "--sandbox", "read-only", "--ephemeral", "--skip-git-repo-check", "--output-schema", str(schema_path), "--output-last-message", str(output_path), "--color", "never", "-C", str(runtime)]
        if run.model:
            command.extend(["--model", run.model])
        if run.profile:
            command.extend(["--profile", run.profile])
        prompt = "Analyze the meeting request in this JSON and return only the required structured result:\n" + json.dumps(run.request_json, ensure_ascii=False)
        started = perf_counter()
        try:
            process = await asyncio.create_subprocess_exec(*command, prompt, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            self._processes[run.id] = process
            stdout, stderr = await asyncio.wait_for(process.communicate(), settings.codex_timeout_seconds)
            if run.status == "cancelled":
                return
            if process.returncode != 0:
                raise RuntimeError(redact(stderr.decode(errors="replace") or stdout.decode(errors="replace")))
            run.status = "validating"
            await db.commit()
            raw = output_path.read_text() if output_path.exists() else stdout.decode(errors="replace")
            try:
                result = CodexOutput.model_validate_json(raw)
            except ValidationError:
                run.retry_count = 1
                repair_path = runs_dir / f"{run.id}-repair.json"
                repair_command = [settings.codex_bin, "exec", "--sandbox", "read-only", "--ephemeral", "--skip-git-repo-check", "--output-schema", str(schema_path), "--output-last-message", str(repair_path), "--color", "never", "-C", str(runtime)]
                repair_prompt = "Repair the following invalid response. Return only JSON matching the output schema, without adding claims:\n" + raw[:12000]
                repair = await asyncio.create_subprocess_exec(*repair_command, repair_prompt, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                self._processes[run.id] = repair
                repair_stdout, repair_stderr = await asyncio.wait_for(repair.communicate(), min(60, settings.codex_timeout_seconds))
                if repair.returncode != 0:
                    raise RuntimeError(redact(repair_stderr.decode(errors="replace")))
                repaired = repair_path.read_text() if repair_path.exists() else repair_stdout.decode(errors="replace")
                result = CodexOutput.model_validate_json(repaired)
            valid_ids = {item["segment_id"] for item in run.request_json["recent_transcript"]}
            if not set(result.evidence_segment_ids).issubset(valid_ids):
                raise ValueError("Codex cited transcript segments outside the request")
            run.response_json = result.model_dump(mode="json")
            await apply_state_patch(db, meeting, result)
            if result.should_suggest and result.suggestion:
                recent = list((await db.scalars(select(Suggestion).where(Suggestion.meeting_id == meeting.id).order_by(desc(Suggestion.created_at)).limit(20))).all())
                if not any(similar(result.suggestion, item.content) for item in recent):
                    suggestion = Suggestion(meeting_id=meeting.id, codex_run_id=run.id, category=result.category, content=result.suggestion, reason=result.reason, follow_up_question=result.follow_up_question, confidence=result.confidence, trigger=run.trigger, evidence_segment_ids_json=result.evidence_segment_ids)
                    db.add(suggestion)
                    await db.flush()
                    await emit(db, meeting.id, "suggestion.created", "codex-worker", {"suggestion_id": suggestion.id, "category": suggestion.category, "content": suggestion.content})
            run.status = "completed"
            await emit(db, meeting.id, "codex.completed", "codex-worker", {"run_id": run.id, "should_suggest": result.should_suggest})
        except asyncio.TimeoutError:
            process = self._processes.get(run.id)
            if process and process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
            run.status, run.sanitized_stderr = "timed_out", "Codex execution timed out"
            await emit(db, meeting.id, "codex.timed_out", "codex-worker", {"run_id": run.id})
        except (RuntimeError, ValueError, ValidationError, OSError) as exc:
            run.status, run.sanitized_stderr = "failed", redact(str(exc))
            await emit(db, meeting.id, "codex.failed", "codex-worker", {"run_id": run.id, "error": run.sanitized_stderr})
        finally:
            self._processes.pop(run.id, None)
            run.ended_at = datetime.now(timezone.utc)
            run.duration_ms = round((perf_counter() - started) * 1000)
            await db.commit()


manager = CodexManager()


async def apply_state_patch(db: AsyncSession, meeting: Meeting, result: CodexOutput) -> None:
    """Apply allowlisted generated additions without replacing user-owned items."""
    patch = result.state_patch
    config = dict(meeting.configuration_json)
    state = dict(config.get("state", {}))
    if patch.current_topic and state.get("current_topic_source") != "user":
        state["current_topic"] = patch.current_topic
        state["current_topic_source"] = "codex"
    model_groups = [
        (Decision, patch.add_decisions, "decisions"),
        (OpenQuestion, patch.add_open_questions, "open_questions"),
        (Risk, patch.add_risks, "risks"),
        (ActionItem, patch.add_action_items, "action_items"),
    ]
    for model, additions, state_key in model_groups:
        existing_rows = list((await db.scalars(select(model).where(model.meeting_id == meeting.id))).all())
        existing = [row.content for row in existing_rows]
        accepted: list[str] = []
        for content in additions:
            if content and not any(similar(content, old) for old in existing):
                db.add(model(meeting_id=meeting.id, content=content, source="codex"))
                existing.append(content); accepted.append(content)
        state[state_key] = list(dict.fromkeys([*state.get(state_key, []), *accepted]))
    state["parking_lot"] = list(dict.fromkeys([*state.get("parking_lot", []), *patch.add_parking_lot]))
    state["version"] = int(state.get("version", 0)) + 1
    state["last_codex_run_at"] = datetime.now(timezone.utc).isoformat()
    config["state"] = state; meeting.configuration_json = config
    db.add(MeetingState(meeting_id=meeting.id, version=state["version"], current_topic=state.get("current_topic", ""), state_json=state, source="codex"))
    await emit(db, meeting.id, "state.updated", "codex-worker", {"version": state["version"]})
