from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.common import HealthResponse
from app.services.system import codex_status, gpu_status, system_status

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="meeting-copilot", version="0.1.0")


@router.get("/system/status")
async def get_system_status(db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    return await system_status(db, settings)


@router.get("/system/gpu")
async def get_gpu_status() -> dict[str, Any]:
    return await gpu_status()


@router.get("/codex/status")
async def get_codex_status(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    return await codex_status(settings)
