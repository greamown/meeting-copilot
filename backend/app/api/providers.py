import asyncio
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.base import ModelProvider
from app.db.session import get_db
from app.schemas.common import ProviderBase, ProviderRead
from app.services.providers import test_provider
from app.services.system import run_command

router = APIRouter()
login_process: asyncio.subprocess.Process | None = None


def provider_read(row: ModelProvider) -> ProviderRead:
    data = ProviderRead.model_validate(row).model_dump()
    data["secret_ref"] = row.secret_ref
    return ProviderRead.model_validate(data)


@router.get("/providers", response_model=list[ProviderRead])
async def list_providers(db: AsyncSession = Depends(get_db)) -> list[ProviderRead]:
    rows = (await db.scalars(select(ModelProvider).order_by(ModelProvider.role, ModelProvider.name))).all()
    return [provider_read(row) for row in rows]


@router.post("/providers", response_model=ProviderRead, status_code=201)
async def create_provider(payload: ProviderBase, db: AsyncSession = Depends(get_db)) -> ProviderRead:
    if await db.get(ModelProvider, payload.id):
        raise HTTPException(409, "Provider id already exists")
    if payload.secret_ref and payload.secret_ref not in os.environ:
        raise HTTPException(422, "Secret reference must name an existing environment variable")
    row = ModelProvider(**payload.model_dump(mode="json", exclude={"extra"}), extra_json=payload.extra)
    db.add(row); await db.commit(); await db.refresh(row)
    return provider_read(row)


@router.get("/providers/{provider_id}", response_model=ProviderRead)
async def get_provider(provider_id: str, db: AsyncSession = Depends(get_db)) -> ProviderRead:
    row = await db.get(ModelProvider, provider_id)
    if not row: raise HTTPException(404, "Provider not found")
    return provider_read(row)


@router.put("/providers/{provider_id}", response_model=ProviderRead)
async def update_provider(provider_id: str, payload: ProviderBase, db: AsyncSession = Depends(get_db)) -> ProviderRead:
    row = await db.get(ModelProvider, provider_id)
    if not row: raise HTTPException(404, "Provider not found")
    if payload.id != provider_id: raise HTTPException(422, "Provider id cannot be changed")
    if payload.secret_ref and payload.secret_ref != row.secret_ref and payload.secret_ref not in os.environ: raise HTTPException(422, "Secret reference must name an existing environment variable")
    values = payload.model_dump(mode="json", exclude={"extra"}); values["extra_json"] = payload.extra
    for key, value in values.items(): setattr(row, key, value)
    await db.commit(); await db.refresh(row); return provider_read(row)


@router.delete("/providers/{provider_id}", status_code=204)
async def delete_provider(provider_id: str, db: AsyncSession = Depends(get_db)) -> None:
    row = await db.get(ModelProvider, provider_id)
    if not row: raise HTTPException(404, "Provider not found")
    await db.delete(row); await db.commit()


@router.post("/providers/{provider_id}/test")
async def test_provider_endpoint(provider_id: str, db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    row = await db.get(ModelProvider, provider_id)
    if not row: raise HTTPException(404, "Provider not found")
    result = await test_provider(row, settings); row.health_status = "healthy" if result["healthy"] else "unhealthy"; row.last_latency_ms = result["latency_ms"]; await db.commit(); return result


@router.post("/providers/{provider_id}/set-default", response_model=ProviderRead)
async def set_default(provider_id: str, db: AsyncSession = Depends(get_db)) -> ProviderRead:
    row = await db.get(ModelProvider, provider_id)
    if not row: raise HTTPException(404, "Provider not found")
    await db.execute(update(ModelProvider).where(ModelProvider.role == row.role).values(is_default=False)); row.is_default = True; await db.commit(); await db.refresh(row); return provider_read(row)


@router.post("/codex/login/start")
async def start_login(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    global login_process
    if login_process and login_process.returncode is None: raise HTTPException(409, "Login already running")
    login_process = await asyncio.create_subprocess_exec(settings.codex_bin, "login", "--device-auth", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    try:
        line = await asyncio.wait_for(login_process.stdout.readline(), 5) if login_process.stdout else b""
    except asyncio.TimeoutError:
        line = b"Login started. Follow the Codex CLI device flow."
    return {"started": True, "message": line.decode(errors="replace")[:1000]}


@router.post("/codex/login/cancel")
async def cancel_login() -> dict[str, bool]:
    global login_process
    if login_process and login_process.returncode is None: login_process.terminate(); await login_process.wait(); return {"cancelled": True}
    return {"cancelled": False}


@router.post("/codex/logout")
async def logout(settings: Settings = Depends(get_settings)) -> dict[str, bool]:
    code, _, _ = await run_command([settings.codex_bin, "logout"]); return {"logged_out": code == 0}


@router.post("/codex/test")
async def test_codex(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    code, output, error = await run_command([settings.codex_bin, "exec", "--sandbox", "read-only", "--ephemeral", "--skip-git-repo-check", "Return exactly: {\"ok\":true}"], timeout=30)
    return {"healthy": code == 0, "output": output[-1000:], "error": error[-1000:]}
