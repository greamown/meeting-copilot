import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import scrub_mapping
from app.db.base import AppSetting, AudioChunk, CodexRun, Event, Meeting, ModelProvider
from app.db.session import get_db
from app.services.system import system_status

router = APIRouter()


class SettingsUpdate(BaseModel):
    periodic_analysis_seconds: int = Field(default=120, ge=30, le=3600)
    minimum_new_characters: int = Field(default=300, ge=20, le=10000)
    codex_cooldown_seconds: int = Field(default=60, ge=0, le=3600)
    suggestion_cooldown_seconds: int = Field(default=180, ge=0, le=7200)
    maximum_recent_transcript_minutes: int = Field(default=10, ge=1, le=120)
    maximum_recent_transcript_characters: int = Field(default=12000, ge=1000, le=100000)
    automatic_analysis_enabled: bool = True
    tts_voice: str = ""
    tts_rate: float = Field(default=1, ge=0.5, le=2)
    tts_volume: float = Field(default=1, ge=0, le=1)


@router.get("/settings", response_model=SettingsUpdate)
async def get_app_settings(db: AsyncSession = Depends(get_db)) -> SettingsUpdate:
    row = await db.scalar(select(AppSetting).where(AppSetting.key == "general"))
    return SettingsUpdate.model_validate(row.value_json if row else {})


@router.put("/settings", response_model=SettingsUpdate)
async def save_app_settings(payload: SettingsUpdate, db: AsyncSession = Depends(get_db)) -> SettingsUpdate:
    row = await db.scalar(select(AppSetting).where(AppSetting.key == "general"))
    if row: row.value_json = payload.model_dump(mode="json")
    else: db.add(AppSetting(key="general", value_json=payload.model_dump(mode="json")))
    await db.commit(); return payload


@router.get("/diagnostics")
async def diagnostics(db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    status = await system_status(db, settings)
    queue_depth = await db.scalar(select(func.count()).select_from(CodexRun).where(CodexRun.status.in_(["queued", "running", "validating"]))) or 0
    active = await db.scalar(select(func.count()).select_from(Meeting).where(Meeting.status == "active")) or 0
    events = list((await db.scalars(select(Event).order_by(desc(Event.created_at)).limit(100))).all())
    providers = list((await db.scalars(select(ModelProvider))).all())
    status.update({"metrics": {"active_meetings": active, "codex_queue_depth": queue_depth, "audio_chunks": await db.scalar(select(func.count()).select_from(AudioChunk)) or 0}, "providers": [{"id": row.id, "name": row.name, "health": row.health_status, "latency_ms": row.last_latency_ms} for row in providers], "events": [{"id": row.id, "meeting_id": row.meeting_id, "sequence": row.sequence, "type": row.type, "source": row.source, "payload": scrub_mapping(row.payload_json), "created_at": row.created_at.isoformat()} for row in events]})
    return status


@router.get("/diagnostics/bundle")
async def diagnostic_bundle(db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)) -> Response:
    data = await diagnostics(db, settings); output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("diagnostics.json", json.dumps(scrub_mapping(data), ensure_ascii=False, indent=2))
        archive.writestr("README.txt", f"Sanitized Meeting Copilot diagnostics generated {datetime.now(timezone.utc).isoformat()}\nNo credential files or environment variables are included.\n")
    return Response(output.getvalue(), media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="meeting-copilot-diagnostics.zip"'})


@router.post("/diagnostics/migrations")
async def validate_migrations(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    tables = (await db.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))).scalars().all() if db.bind and db.bind.dialect.name == "sqlite" else []
    required = {"meetings", "transcript_segments", "codex_runs", "suggestions", "events", "model_providers"}
    return {"valid": required.issubset(set(tables)), "missing": sorted(required - set(tables))}
