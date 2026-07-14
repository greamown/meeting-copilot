import io
import json
import zipfile
from datetime import UTC, datetime
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import scrub_mapping
from app.db.base import (
    AppSetting,
    AudioChunk,
    CodexRun,
    Event,
    Meeting,
    ModelProvider,
    Suggestion,
)
from app.db.session import get_db
from app.services.auth import add_audit
from app.services.events import hub
from app.services.system import system_status

router = APIRouter()


def _mean_event_value(events: list[Event], event_type: str, field: str) -> float | None:
    values = [
        float(row.payload_json[field])
        for row in events
        if row.type == event_type and isinstance(row.payload_json.get(field), (int, float))
    ]
    return round(sum(values) / len(values), 3) if values else None


async def _stt_queue_depth(settings: Settings) -> int:
    if not settings.stt_worker_url or not settings.worker_token():
        return 0
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.get(
                f"{settings.stt_worker_url.rstrip('/')}/health",
                headers={"X-Worker-Token": settings.worker_token()},
            )
        response.raise_for_status()
        return int(response.json().get("queue_depth", 0))
    except (httpx.HTTPError, TypeError, ValueError):
        return 0


class SettingsUpdate(BaseModel):
    setup_completed: bool = False
    ui_language: Literal["zh-TW", "zh-CN", "en", "ja", "ko"] = "zh-TW"
    meeting_input_language: Literal["auto", "zh-TW", "zh-CN", "en", "ja", "ko"] = "auto"
    secondary_meeting_language: Literal["none", "zh-TW", "zh-CN", "en", "ja", "ko"] = "none"
    transcript_display_language: Literal["original", "zh-TW", "zh-CN", "en", "ja", "ko"] = (
        "original"
    )
    translation_language: Literal["none", "zh-TW", "zh-CN", "en", "ja", "ko"] = "none"
    suggestion_output_language: Literal["zh-TW", "zh-CN", "en", "ja", "ko"] = "zh-TW"
    summary_output_language: Literal["zh-TW", "zh-CN", "en", "ja", "ko"] = "zh-TW"
    export_language: Literal["original", "zh-TW", "zh-CN", "en", "ja", "ko"] = "original"
    tts_language: Literal["zh-TW", "zh-CN", "en", "ja", "ko"] = "zh-TW"
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
async def save_app_settings(
    payload: SettingsUpdate, request: Request, db: AsyncSession = Depends(get_db)
) -> SettingsUpdate:
    row = await db.scalar(select(AppSetting).where(AppSetting.key == "general"))
    if row:
        row.value_json = payload.model_dump(mode="json")
    else:
        db.add(AppSetting(key="general", value_json=payload.model_dump(mode="json")))
    identity = getattr(request.state, "identity", None)
    add_audit(
        db,
        identity.username if identity else "local-user",
        "settings.update",
        "app_setting",
        "general",
        {"fields": sorted(payload.model_fields_set)},
    )
    await db.commit()
    return payload


@router.get("/diagnostics")
async def diagnostics(
    db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)
) -> dict[str, Any]:
    status = await system_status(db, settings)
    queue_depth = (
        await db.scalar(
            select(func.count())
            .select_from(CodexRun)
            .where(CodexRun.status.in_(["queued", "running", "validating"]))
        )
        or 0
    )
    active = (
        await db.scalar(select(func.count()).select_from(Meeting).where(Meeting.status == "active"))
        or 0
    )
    events = list(
        (await db.scalars(select(Event).order_by(desc(Event.created_at)).limit(100))).all()
    )
    metric_events = list(
        (await db.scalars(select(Event).order_by(desc(Event.created_at)).limit(2000))).all()
    )
    event_counts: dict[str, int] = {
        str(name): int(count)
        for name, count in (
            await db.execute(select(Event.type, func.count()).group_by(Event.type))
        ).all()
    }
    codex_counts: dict[str, int] = {
        str(status_name): int(count)
        for status_name, count in (
            await db.execute(select(CodexRun.status, func.count()).group_by(CodexRun.status))
        ).all()
    }
    suggestion_counts: dict[str, int] = {
        str(status_name): int(count)
        for status_name, count in (
            await db.execute(select(Suggestion.status, func.count()).group_by(Suggestion.status))
        ).all()
    }
    codex_finished = (
        codex_counts.get("completed", 0)
        + codex_counts.get("failed", 0)
        + codex_counts.get("timed_out", 0)
    )
    codex_latency = await db.scalar(
        select(func.avg(CodexRun.duration_ms)).where(CodexRun.duration_ms.is_not(None))
    )
    providers = list((await db.scalars(select(ModelProvider))).all())
    status.update(
        {
            "metrics": {
                "active_meetings": active,
                "codex_queue_depth": queue_depth,
                "audio_chunks": await db.scalar(select(func.count()).select_from(AudioChunk)) or 0,
                "audio_chunks_received": int(event_counts.get("audio.chunk.received", 0)),
                "audio_chunks_dropped": int(event_counts.get("audio.chunk.dropped", 0)),
                "stt_latency_ms": _mean_event_value(metric_events, "stt.completed", "latency_ms"),
                "stt_real_time_factor": _mean_event_value(
                    metric_events, "stt.completed", "real_time_factor"
                ),
                "stt_queue_depth": await _stt_queue_depth(settings),
                "codex_latency_ms": round(float(codex_latency), 2) if codex_latency else None,
                "codex_success_rate": round(
                    int(codex_counts.get("completed", 0)) / codex_finished, 4
                )
                if codex_finished
                else None,
                "codex_failure_rate": round(
                    int(codex_counts.get("failed", 0)) / codex_finished, 4
                )
                if codex_finished
                else None,
                "codex_timeout_rate": round(
                    int(codex_counts.get("timed_out", 0)) / codex_finished, 4
                )
                if codex_finished
                else None,
                "suggestions_generated": int(event_counts.get("suggestion.created", 0)),
                "suggestions_accepted": int(suggestion_counts.get("accepted", 0)),
                "suggestions_ignored": int(suggestion_counts.get("ignored", 0)),
                "duplicate_suggestions_suppressed": int(
                    event_counts.get("suggestion.duplicate_suppressed", 0)
                ),
                "tts_latency_ms": _mean_event_value(metric_events, "tts.completed", "latency_ms"),
                "websocket_connections": hub.connection_count,
            },
            "providers": [
                {
                    "id": row.id,
                    "name": row.name,
                    "health": row.health_status,
                    "latency_ms": row.last_latency_ms,
                }
                for row in providers
            ],
            "events": [
                {
                    "id": row.id,
                    "meeting_id": row.meeting_id,
                    "sequence": row.sequence,
                    "type": row.type,
                    "source": row.source,
                    "payload": scrub_mapping(row.payload_json),
                    "created_at": row.created_at.isoformat(),
                }
                for row in events
            ],
        }
    )
    return status


@router.get("/metrics")
async def metrics(
    db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)
) -> dict[str, Any]:
    data = await diagnostics(db, settings)
    return {
        **data["metrics"],
        "database_latency_ms": data["database"]["latency_ms"],
        "redis_latency_ms": data["redis"]["latency_ms"],
        "gpu": data["gpu"],
    }


@router.get("/diagnostics/bundle")
async def diagnostic_bundle(
    db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)
) -> Response:
    data = await diagnostics(db, settings)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "diagnostics.json", json.dumps(scrub_mapping(data), ensure_ascii=False, indent=2)
        )
        archive.writestr(
            "README.txt",
            "Sanitized Meeting Copilot diagnostics generated "
            f"{datetime.now(UTC).isoformat()}\n"
            "No credential files or environment variables are included.\n",
        )
    return Response(
        output.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="meeting-copilot-diagnostics.zip"'},
    )


@router.post("/diagnostics/migrations")
async def validate_migrations(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    dialect = db.bind.dialect.name if db.bind else ""
    if dialect == "sqlite":
        query = text("SELECT name FROM sqlite_master WHERE type='table'")
    elif dialect == "postgresql":
        query = text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    else:
        return {"valid": False, "missing": [], "error": f"Unsupported database: {dialect}"}
    tables = (await db.execute(query)).scalars().all()
    required = {
        "meetings",
        "transcript_segments",
        "codex_runs",
        "suggestions",
        "events",
        "model_providers",
        "idempotency_records",
    }
    return {"valid": required.issubset(set(tables)), "missing": sorted(required - set(tables))}
