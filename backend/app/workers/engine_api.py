import asyncio
import json
import re
import shutil
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field, ValidationError
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.security import redact, scrub_mapping
from app.core.worker_auth import require_worker_token
from app.schemas.meeting import CodexOutput
from app.services.codex import AGENT_INSTRUCTIONS
from app.services.system import run_command

settings = get_settings()
locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
processes: dict[str, asyncio.subprocess.Process] = {}
login_process: asyncio.subprocess.Process | None = None
login_output: list[str] = []
login_reader_task: asyncio.Task[None] | None = None
ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


class ExecuteRequest(BaseModel):
    run_id: str
    meeting_id: str
    request: dict[str, Any]
    profile: str | None = None
    model: str | None = None
    timeout_seconds: int = Field(default=180, ge=1, le=900)


class ExecuteResponse(BaseModel):
    result: CodexOutput
    retry_count: int
    duration_ms: int


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings.runtime_dir.mkdir(parents=True, exist_ok=True)
    yield
    for process in list(processes.values()):
        if process.returncode is None:
            process.terminate()
    if login_process and login_process.returncode is None:
        login_process.terminate()


def clean_login_line(line: str) -> str:
    line = ANSI_ESCAPE.sub("", line)
    if "could not create PATH aliases" in line:
        return ""
    return redact(line).strip()


def clean_cli_output(value: str) -> str:
    return "\n".join(cleaned for line in value.splitlines() if (cleaned := clean_login_line(line)))


async def collect_login_output(process: asyncio.subprocess.Process) -> None:
    if not process.stdout:
        return
    while line := await process.stdout.readline():
        cleaned = clean_login_line(line.decode(errors="replace"))
        if cleaned:
            login_output.append(cleaned)
            del login_output[:-20]


def login_snapshot() -> dict[str, object]:
    running = bool(login_process and login_process.returncode is None)
    return {
        "started": login_process is not None,
        "running": running,
        "completed": bool(login_process and login_process.returncode == 0),
        "message": "\n".join(login_output),
    }


app = FastAPI(title="Meeting Copilot Codex Worker", lifespan=lifespan)


@asynccontextmanager
async def meeting_lock(meeting_id: str, timeout_seconds: int) -> AsyncIterator[None]:
    async with locks[meeting_id]:
        if not settings.redis_url:
            yield
            return
        client: Any = Redis.from_url(settings.redis_url, decode_responses=True)
        key = f"meeting-copilot:codex-lock:{meeting_id}"
        owner = str(uuid4())
        acquired = False
        try:
            deadline = asyncio.get_running_loop().time() + 10
            while not await client.set(key, owner, ex=timeout_seconds + 120, nx=True):
                if asyncio.get_running_loop().time() >= deadline:
                    raise HTTPException(409, "Another Codex job is active for this meeting")
                await asyncio.sleep(0.2)
            acquired = True
            yield
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(503, "Redis lock unavailable") from exc
        finally:
            try:
                if acquired:
                    await client.eval(
                        "if redis.call('get', KEYS[1]) == ARGV[1] then "
                        "return redis.call('del', KEYS[1]) else return 0 end",
                        1,
                        key,
                        owner,
                    )
            finally:
                await client.aclose()


def command_for(payload: ExecuteRequest, runtime: Path, output: Path) -> list[str]:
    schema = Path("/app/schemas/codex-response.schema.json")
    command = [
        settings.codex_bin,
        "exec",
        "--sandbox",
        "read-only",
        "--ephemeral",
        "--skip-git-repo-check",
        "--output-schema",
        str(schema),
        "--output-last-message",
        str(output),
        "--color",
        "never",
        "-C",
        str(runtime),
    ]
    if payload.model:
        command.extend(["--model", payload.model])
    if payload.profile:
        command.extend(["--profile", payload.profile])
    return command


async def invoke(
    payload: ExecuteRequest, command: list[str], prompt: str, output: Path, timeout: int
) -> str:
    process = await asyncio.create_subprocess_exec(
        *command, prompt, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    processes[payload.run_id] = process
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
    except TimeoutError:
        if process.returncode is None:
            process.kill()
        raise HTTPException(504, "Codex execution timed out") from None
    finally:
        processes.pop(payload.run_id, None)
    if process.returncode != 0:
        raise HTTPException(
            502, redact(stderr.decode(errors="replace") or stdout.decode(errors="replace"))
        )
    return output.read_text() if output.exists() else stdout.decode(errors="replace")


@app.get("/health")
async def health() -> dict[str, object]:
    path = shutil.which(settings.codex_bin)
    return {
        "status": "ok" if path else "degraded",
        "codex_installed": bool(path),
        "active_jobs": len(processes),
        "queued_meetings": sum(lock.locked() for lock in locks.values()),
    }


@app.get("/v1/status", dependencies=[Depends(require_worker_token)])
async def status() -> dict[str, object]:
    path = shutil.which(settings.codex_bin)
    if not path:
        return {
            "installed": False,
            "authenticated": False,
            "version": None,
            "provider": "codex_cli",
            "error": "Codex CLI not found",
        }
    version_code, version, version_error = await run_command([path, "--version"])
    auth_code, auth_output, auth_error = await run_command([path, "login", "status"])
    return {
        "installed": version_code == 0,
        "authenticated": auth_code == 0,
        "version": version.strip() or None,
        "profile": settings.codex_profile,
        "model": settings.codex_model,
        "provider": "codex_cli",
        "error": clean_cli_output(version_error or auth_error),
        "status": clean_cli_output(auth_output),
    }


@app.post(
    "/v1/execute", response_model=ExecuteResponse, dependencies=[Depends(require_worker_token)]
)
async def execute(payload: ExecuteRequest) -> ExecuteResponse:
    async with meeting_lock(payload.meeting_id, payload.timeout_seconds):
        runtime = settings.runtime_dir / "meetings" / payload.meeting_id
        runs = runtime / "runs"
        runs.mkdir(parents=True, exist_ok=True)
        runtime.joinpath("AGENTS.md").write_text(AGENT_INSTRUCTIONS)
        runtime.joinpath("request.json").write_text(
            json.dumps(scrub_mapping(payload.request), ensure_ascii=False, indent=2)
        )
        output = runs / f"{payload.run_id}-response.json"
        prompt = (
            "Analyze the meeting request in this JSON and return only the required "
            "structured result:\n" + json.dumps(payload.request, ensure_ascii=False)
        )
        started = perf_counter()
        raw = await invoke(
            payload, command_for(payload, runtime, output), prompt, output, payload.timeout_seconds
        )
        retry_count = 0
        try:
            result = CodexOutput.model_validate_json(raw)
        except ValidationError:
            retry_count = 1
            repair_output = runs / f"{payload.run_id}-repair.json"
            repair_prompt = (
                "Repair this invalid response. Return only schema-conforming JSON without "
                "adding claims:\n" + raw[:12000]
            )
            repaired = await invoke(
                payload,
                command_for(payload, runtime, repair_output),
                repair_prompt,
                repair_output,
                min(60, payload.timeout_seconds),
            )
            try:
                result = CodexOutput.model_validate_json(repaired)
            except ValidationError as exc:
                raise HTTPException(
                    422, "Codex returned invalid JSON after one repair attempt"
                ) from exc
        valid_ids = {
            item.get("segment_id") for item in payload.request.get("recent_transcript", [])
        }
        if not set(result.evidence_segment_ids).issubset(valid_ids):
            raise HTTPException(422, "Codex cited transcript segments outside the request")
        return ExecuteResponse(
            result=result,
            retry_count=retry_count,
            duration_ms=round((perf_counter() - started) * 1000),
        )


@app.post("/v1/jobs/{run_id}/cancel", dependencies=[Depends(require_worker_token)])
async def cancel(run_id: str) -> dict[str, bool]:
    process = processes.get(run_id)
    if not process or process.returncode is not None:
        return {"cancelled": False}
    try:
        process.terminate()
        await asyncio.wait_for(process.wait(), 5)
    except ProcessLookupError:
        pass
    except TimeoutError:
        try:
            process.kill()
        except ProcessLookupError:
            pass
    return {"cancelled": True}


@app.post("/v1/login/start", dependencies=[Depends(require_worker_token)])
async def login_start() -> dict[str, object]:
    global login_process, login_reader_task
    if login_process and login_process.returncode is None:
        return login_snapshot()
    login_output.clear()
    login_process = await asyncio.create_subprocess_exec(
        settings.codex_bin,
        "login",
        "--device-auth",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    login_reader_task = asyncio.create_task(collect_login_output(login_process))
    for _ in range(30):
        if login_output or login_process.returncode is not None:
            break
        await asyncio.sleep(0.1)
    return login_snapshot()


@app.get("/v1/login/status", dependencies=[Depends(require_worker_token)])
async def login_status() -> dict[str, object]:
    return login_snapshot()


@app.post("/v1/login/cancel", dependencies=[Depends(require_worker_token)])
async def login_cancel() -> dict[str, bool]:
    global login_process
    if login_process and login_process.returncode is None:
        login_process.terminate()
        await login_process.wait()
        if login_reader_task:
            await login_reader_task
        return {"cancelled": True}
    return {"cancelled": False}


@app.post("/v1/logout", dependencies=[Depends(require_worker_token)])
async def logout() -> dict[str, bool]:
    code, _, _ = await run_command([settings.codex_bin, "logout"])
    return {"logged_out": code == 0}


@app.post("/v1/test", dependencies=[Depends(require_worker_token)])
async def test() -> dict[str, object]:
    code, output, error = await run_command(
        [
            settings.codex_bin,
            "exec",
            "--sandbox",
            "read-only",
            "--ephemeral",
            "--skip-git-repo-check",
            'Return exactly: {"ok":true}',
        ],
        timeout=30,
    )
    return {
        "healthy": code == 0,
        "output": clean_cli_output(output[-1000:]),
        "error": "" if code == 0 else clean_cli_output(error[-1000:]),
    }
