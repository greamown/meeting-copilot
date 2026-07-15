import asyncio
import os
from typing import Any, cast

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import scrub_mapping
from app.db.base import AppSetting, ModelProvider
from app.db.session import get_db
from app.schemas.common import ProviderBase, ProviderRead
from app.services.auth import add_audit
from app.services.providers import test_provider
from app.services.system import run_command

router = APIRouter()
login_process: asyncio.subprocess.Process | None = None


def audit_provider(db: AsyncSession, request: Request, action: str, row: ModelProvider) -> None:
    identity = getattr(request.state, "identity", None)
    add_audit(
        db,
        identity.username if identity else "local-user",
        action,
        "model_provider",
        row.id,
        {"role": row.role, "provider_type": row.provider_type},
    )


async def worker_action(settings: Settings, path: str) -> dict[str, Any]:
    token = settings.worker_token()
    if not settings.cli_worker_url or not token:
        raise HTTPException(503, "CLI worker is not configured")
    try:
        async with httpx.AsyncClient(timeout=40) as client:
            response = await client.post(
                f"{settings.cli_worker_url.rstrip('/')}{path}", headers={"X-Worker-Token": token}
            )
        if not response.is_success:
            raise HTTPException(
                response.status_code, response.json().get("detail", "CLI worker request failed")
            )
        return cast(dict[str, Any], response.json())
    except httpx.HTTPError as exc:
        raise HTTPException(503, f"CLI worker unavailable: {type(exc).__name__}") from exc


async def worker_status(settings: Settings, path: str) -> dict[str, Any]:
    token = settings.worker_token()
    if not settings.cli_worker_url or not token:
        raise HTTPException(503, "CLI worker is not configured")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{settings.cli_worker_url.rstrip('/')}{path}",
                headers={"X-Worker-Token": token},
            )
        if not response.is_success:
            raise HTTPException(
                response.status_code, response.json().get("detail", "CLI worker request failed")
            )
        return cast(dict[str, Any], response.json())
    except httpx.HTTPError as exc:
        raise HTTPException(503, f"CLI worker unavailable: {type(exc).__name__}") from exc


def provider_read(row: ModelProvider) -> ProviderRead:
    data = ProviderRead.model_validate(row).model_dump()
    data["secret_ref"] = row.secret_ref
    return ProviderRead.model_validate(data)


@router.get("/providers", response_model=list[ProviderRead])
async def list_providers(db: AsyncSession = Depends(get_db)) -> list[ProviderRead]:
    rows = (
        await db.scalars(select(ModelProvider).order_by(ModelProvider.role, ModelProvider.name))
    ).all()
    return [provider_read(row) for row in rows]


@router.post("/providers", response_model=ProviderRead, status_code=201)
async def create_provider(
    payload: ProviderBase, request: Request, db: AsyncSession = Depends(get_db)
) -> ProviderRead:
    if await db.get(ModelProvider, payload.id):
        raise HTTPException(409, "Provider id already exists")
    if payload.secret_ref and payload.secret_ref not in os.environ:
        raise HTTPException(422, "Secret reference must name an existing environment variable")
    row = ModelProvider(
        **payload.model_dump(mode="json", exclude={"extra"}), extra_json=payload.extra
    )
    db.add(row)
    audit_provider(db, request, "provider.create", row)
    await db.commit()
    await db.refresh(row)
    return provider_read(row)


@router.get("/providers/{provider_id}", response_model=ProviderRead)
async def get_provider(provider_id: str, db: AsyncSession = Depends(get_db)) -> ProviderRead:
    row = await db.get(ModelProvider, provider_id)
    if not row:
        raise HTTPException(404, "Provider not found")
    return provider_read(row)


@router.put("/providers/{provider_id}", response_model=ProviderRead)
async def update_provider(
    provider_id: str,
    payload: ProviderBase,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ProviderRead:
    row = await db.get(ModelProvider, provider_id)
    if not row:
        raise HTTPException(404, "Provider not found")
    if payload.id != provider_id:
        raise HTTPException(422, "Provider id cannot be changed")
    if (
        payload.secret_ref
        and payload.secret_ref != row.secret_ref
        and payload.secret_ref not in os.environ
    ):
        raise HTTPException(422, "Secret reference must name an existing environment variable")
    values = payload.model_dump(mode="json", exclude={"extra"})
    values["extra_json"] = payload.extra
    for key, value in values.items():
        setattr(row, key, value)
    audit_provider(db, request, "provider.update", row)
    await db.commit()
    await db.refresh(row)
    return provider_read(row)


@router.delete("/providers/{provider_id}", status_code=204)
async def delete_provider(
    provider_id: str, request: Request, db: AsyncSession = Depends(get_db)
) -> None:
    row = await db.get(ModelProvider, provider_id)
    if not row:
        raise HTTPException(404, "Provider not found")
    audit_provider(db, request, "provider.delete", row)
    await db.delete(row)
    await db.commit()


@router.post("/providers/{provider_id}/test")
async def test_provider_endpoint(
    provider_id: str, db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)
) -> dict[str, Any]:
    row = await db.get(ModelProvider, provider_id)
    if not row:
        raise HTTPException(404, "Provider not found")
    result = await test_provider(row, settings)
    row.health_status = "healthy" if result["healthy"] else "unhealthy"
    row.last_latency_ms = result["latency_ms"]
    await db.commit()
    return result


@router.post("/providers/{provider_id}/toggle", response_model=ProviderRead)
async def toggle_provider(
    provider_id: str, request: Request, db: AsyncSession = Depends(get_db)
) -> ProviderRead:
    row = await db.get(ModelProvider, provider_id)
    if not row:
        raise HTTPException(404, "Provider not found")
    row.enabled = not row.enabled
    if not row.enabled:
        row.is_default = False
    audit_provider(db, request, "provider.toggle", row)
    await db.commit()
    await db.refresh(row)
    return provider_read(row)


@router.post("/providers/{provider_id}/set-default", response_model=ProviderRead)
async def set_default(
    provider_id: str, request: Request, db: AsyncSession = Depends(get_db)
) -> ProviderRead:
    row = await db.get(ModelProvider, provider_id)
    if not row:
        raise HTTPException(404, "Provider not found")
    if not row.enabled:
        raise HTTPException(409, "Disabled provider cannot be the default")
    await db.execute(
        update(ModelProvider).where(ModelProvider.role == row.role).values(is_default=False)
    )
    row.is_default = True
    audit_provider(db, request, "provider.set_default", row)
    await db.commit()
    await db.refresh(row)
    return provider_read(row)


@router.post("/codex/login/start")
async def start_login(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    if settings.cli_worker_url:
        return await worker_action(settings, "/v1/login/start")
    global login_process
    if login_process and login_process.returncode is None:
        raise HTTPException(409, "Login already running")
    login_process = await asyncio.create_subprocess_exec(
        settings.codex_bin,
        "login",
        "--device-auth",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        line = (
            await asyncio.wait_for(login_process.stdout.readline(), 5)
            if login_process.stdout
            else b""
        )
    except TimeoutError:
        line = b"Login started. Follow the Codex CLI device flow."
    return {"started": True, "message": line.decode(errors="replace")[:1000]}


@router.get("/codex/login/status")
async def get_login_status(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    if settings.cli_worker_url:
        return await worker_status(settings, "/v1/login/status")
    running = bool(login_process and login_process.returncode is None)
    return {"started": login_process is not None, "running": running, "message": ""}


@router.post("/codex/login/cancel")
async def cancel_login(settings: Settings = Depends(get_settings)) -> dict[str, bool]:
    if settings.cli_worker_url:
        return await worker_action(settings, "/v1/login/cancel")
    global login_process
    if login_process and login_process.returncode is None:
        login_process.terminate()
        await login_process.wait()
        return {"cancelled": True}
    return {"cancelled": False}


@router.post("/codex/logout")
async def logout(settings: Settings = Depends(get_settings)) -> dict[str, bool]:
    if settings.cli_worker_url:
        return await worker_action(settings, "/v1/logout")
    code, _, _ = await run_command([settings.codex_bin, "logout"])
    return {"logged_out": code == 0}


@router.post("/codex/test")
async def test_codex(
    settings: Settings = Depends(get_settings), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    if settings.cli_worker_url:
        result = await worker_action(settings, "/v1/test")
    else:
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
        result = {"healthy": code == 0, "output": output[-1000:], "error": error[-1000:]}
    sanitized = cast(dict[str, Any], scrub_mapping(result))
    row = await db.scalar(select(AppSetting).where(AppSetting.key == "codex_last_test"))
    if row:
        row.value_json = sanitized
    else:
        db.add(AppSetting(key="codex_last_test", value_json=sanitized))
    await db.commit()
    return sanitized


# --- Claude Code (claude CLI) auth: local-only, mirrors the codex flow above.
# ponytail: no remote-worker path for claude yet; add a claude_worker_url branch if it ever
# runs off-box, like cli_worker_url does.
claude_login_process: asyncio.subprocess.Process | None = None


async def _collect_output(stream: asyncio.StreamReader | None, budget: float) -> str:
    """Read whatever the process prints within `budget` seconds (e.g. the login URL)."""
    if not stream:
        return ""
    out = b""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + budget
    while len(out) < 2000 and (remaining := deadline - loop.time()) > 0:
        try:
            line = await asyncio.wait_for(stream.readline(), remaining)
        except TimeoutError:
            break
        if not line:
            break
        out += line
    return out.decode(errors="replace")[:1000]


@router.post("/claude/login/start")
async def start_claude_login(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    if settings.cli_worker_url:
        return await worker_action(settings, "/v1/login/start?engine=claude")
    global claude_login_process
    if claude_login_process and claude_login_process.returncode is None:
        raise HTTPException(409, "Login already running")
    claude_login_process = await asyncio.create_subprocess_exec(
        settings.claude_bin,
        "auth",
        "login",
        "--claudeai",
        stdin=asyncio.subprocess.PIPE,  # OAuth prompts "Paste code here" on stdin
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    message = await _collect_output(claude_login_process.stdout, 4)
    return {"started": True, "message": message or "Login started. Follow the Claude Code sign-in."}


@router.get("/claude/login/status")
async def get_claude_login_status(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    if settings.cli_worker_url:
        return await worker_status(settings, "/v1/login/status?engine=claude")
    running = bool(claude_login_process and claude_login_process.returncode is None)
    return {"started": claude_login_process is not None, "running": running, "message": ""}


@router.post("/claude/login/cancel")
async def cancel_claude_login(settings: Settings = Depends(get_settings)) -> dict[str, bool]:
    if settings.cli_worker_url:
        return cast(dict[str, bool], await worker_action(settings, "/v1/login/cancel?engine=claude"))
    global claude_login_process
    if claude_login_process and claude_login_process.returncode is None:
        claude_login_process.terminate()
        await claude_login_process.wait()
        return {"cancelled": True}
    return {"cancelled": False}


@router.post("/claude/logout")
async def logout_claude(settings: Settings = Depends(get_settings)) -> dict[str, bool]:
    if settings.cli_worker_url:
        return cast(dict[str, bool], await worker_action(settings, "/v1/logout?engine=claude"))
    code, _, _ = await run_command([settings.claude_bin, "auth", "logout"])
    return {"logged_out": code == 0}


@router.post("/claude/test")
async def test_claude(
    settings: Settings = Depends(get_settings), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    if settings.cli_worker_url:
        result = await worker_action(settings, "/v1/test?engine=claude")
    else:
        code, output, error = await run_command(
            [settings.claude_bin, "-p", 'Return exactly: {"ok":true}', "--output-format", "json"],
            timeout=30,
        )
        result = {"healthy": code == 0, "output": output[-1000:], "error": error[-1000:]}
    sanitized = cast(dict[str, Any], scrub_mapping(result))
    row = await db.scalar(select(AppSetting).where(AppSetting.key == "claude_last_test"))
    if row:
        row.value_json = sanitized
    else:
        db.add(AppSetting(key="claude_last_test", value_json=sanitized))
    await db.commit()
    return sanitized


class ClaudeLoginCode(BaseModel):
    code: str = Field(min_length=1, max_length=2000)


@router.post("/claude/login/submit")
async def submit_claude_login(
    payload: ClaudeLoginCode, settings: Settings = Depends(get_settings)
) -> dict[str, bool]:
    if settings.cli_worker_url:
        token = settings.worker_token()
        if not token:
            raise HTTPException(503, "CLI worker is not configured")
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{settings.cli_worker_url.rstrip('/')}/v1/login/submit",
                    headers={"X-Worker-Token": token},
                    json={"code": payload.code},
                )
            if not response.is_success:
                raise HTTPException(response.status_code, "Claude login submit failed")
            return cast(dict[str, bool], response.json())
        except httpx.HTTPError as exc:
            raise HTTPException(503, f"Claude worker unavailable: {type(exc).__name__}") from exc
    proc = claude_login_process
    if proc and proc.returncode is None and proc.stdin:
        proc.stdin.write((payload.code.strip() + "\n").encode())
        await proc.stdin.drain()
        return {"submitted": True}
    return {"submitted": False}
