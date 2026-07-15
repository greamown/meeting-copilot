from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.base import AppSetting
from app.db.session import get_db
from app.schemas.common import HealthResponse
from app.services.system import claude_status, codex_status, gpu_status, system_status

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="meeting-copilot", version="0.1.0")


@router.get("/live")
async def liveness() -> dict[str, str]:
    return {"status": "ok", "service": "meeting-copilot"}


@router.get("/ready")
async def readiness(
    db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)
) -> JSONResponse:
    checks: dict[str, bool] = {"database": False, "redis": not bool(settings.redis_url)}
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass
    if settings.redis_url:
        client: Redis = Redis.from_url(settings.redis_url)
        try:
            checks["redis"] = bool(await client.ping())
        except Exception:
            checks["redis"] = False
        finally:
            await client.aclose()
    ready = all(checks.values())
    return JSONResponse(
        {"status": "ok" if ready else "not_ready", "checks": checks},
        status_code=200 if ready else 503,
    )


@router.get("/system/status")
async def get_system_status(
    db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)
) -> dict[str, Any]:
    return await system_status(db, settings)


@router.get("/system/gpu")
async def get_gpu_status() -> dict[str, Any]:
    return await gpu_status(get_settings())


@router.get("/codex/status")
async def get_codex_status(
    settings: Settings = Depends(get_settings), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    status = await codex_status(settings)
    last_test = await db.scalar(select(AppSetting).where(AppSetting.key == "codex_last_test"))
    status["last_test"] = last_test.value_json if last_test else None
    return status


@router.get("/claude/status")
async def get_claude_status(
    settings: Settings = Depends(get_settings), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    status = await claude_status(settings)
    last_test = await db.scalar(select(AppSetting).where(AppSetting.key == "claude_last_test"))
    status["last_test"] = last_test.value_json if last_test else None
    return status
