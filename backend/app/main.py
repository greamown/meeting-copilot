import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import update

from app.api.auth import router as auth_router
from app.api.diagnostics import router as diagnostics_router
from app.api.knowledge import router as knowledge_router
from app.api.meetings import router as meetings_router
from app.api.projects import router as projects_router
from app.api.providers import router as providers_router
from app.api.system import router as system_router
from app.api.work_items import router as work_items_router
from app.core.config import get_settings
from app.db.base import Base, CodexRun, Meeting, ModelProvider
from app.db.session import SessionLocal, engine
from app.services.auth import remote_auth_applies, request_identity, verify_csrf
from app.services.codex import manager as codex_manager

settings = get_settings()
logger = logging.getLogger("meeting_copilot")
logging.basicConfig(level=logging.INFO, format="%(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings.runtime_dir.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        await session.execute(
            update(Meeting)
            .where(Meeting.status.in_(["active", "paused"]))
            .values(status="interrupted")
        )
        await session.execute(
            update(CodexRun)
            .where(CodexRun.status.in_(["queued", "preparing_context", "running", "validating"]))
            .values(status="failed", sanitized_stderr="Worker restarted")
        )
        defaults: list[dict[str, Any]] = [
            {
                "id": "codex-local",
                "name": "Codex CLI",
                "role": "reasoning",
                "provider_type": "codex_cli",
                "model": settings.codex_model,
                "is_default": True,
                "extra_json": {
                    "sandbox": "read-only",
                    "approval_policy": "never",
                    "network_access": False,
                    "repository_access": False,
                },
            },
            {
                "id": "local-stt-primary",
                "name": "Local Whisper",
                "role": "stt",
                "provider_type": "local_faster_whisper",
                "model": settings.stt_model,
                "is_default": True,
                "extra_json": {
                    "device": settings.stt_device,
                    "compute_type": settings.stt_compute_type,
                    "language": "zh",
                    "vad_filter": True,
                },
            },
            {
                "id": "browser-tts",
                "name": "Browser Speech",
                "role": "tts",
                "provider_type": "browser_speech_synthesis",
                "model": None,
                "is_default": True,
                "extra_json": {},
            },
        ]
        if settings.tts_worker_url:
            defaults.append(
                {
                    "id": "local-tts-worker",
                    "name": "Local TTS Worker",
                    "role": "tts",
                    "provider_type": "openai_compatible_tts",
                    "base_url": settings.tts_worker_url.rstrip("/") + "/v1",
                    "model": "espeak-ng",
                    "enabled": True,
                    "is_default": False,
                    "extra_json": {"voice": "zh", "response_format": "wav"},
                }
            )
        for values in defaults:
            if not await session.get(ModelProvider, values["id"]):
                session.add(ModelProvider(**values))
        await session.commit()
    try:
        yield
    finally:
        await codex_manager.shutdown()
        await engine.dispose()


app = FastAPI(title="Meeting Copilot API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID", "X-Idempotency-Key"],
)
app.include_router(system_router, prefix="/api", tags=["system"])
app.include_router(auth_router, prefix="/api", tags=["auth"])
app.include_router(providers_router, prefix="/api", tags=["providers"])
app.include_router(projects_router, prefix="/api", tags=["projects"])
app.include_router(meetings_router, prefix="/api", tags=["meetings"])
app.include_router(work_items_router, prefix="/api", tags=["work-items"])
app.include_router(knowledge_router, prefix="/api", tags=["knowledge"])
app.include_router(diagnostics_router, prefix="/api", tags=["diagnostics"])


@app.middleware("http")
async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = request.headers.get("X-Request-ID", str(uuid4()))[:100]
    started = perf_counter()
    content_length = request.headers.get("content-length")
    if request.method in {"POST", "PUT", "PATCH"} and content_length:
        try:
            if int(content_length) > settings.max_request_body_bytes:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Request body is too large"},
                    headers={"X-Request-ID": request_id},
                )
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid Content-Length header"},
                headers={"X-Request-ID": request_id},
            )
    exempt = request.url.path in {
        "/api/health",
        "/api/live",
        "/api/ready",
        "/api/auth/status",
        "/api/auth/bootstrap",
        "/api/auth/login",
    }
    if remote_auth_applies(request.url.hostname, settings) and not exempt:
        async with SessionLocal() as session:
            identity = await request_identity(request, session)
            if not identity:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Authentication required for remote access"},
                    headers={"X-Request-ID": request_id},
                )
            if request.method not in {"GET", "HEAD", "OPTIONS"} and not verify_csrf(
                identity, request.headers.get("X-CSRF-Token")
            ):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Invalid CSRF token"},
                    headers={"X-Request-ID": request_id},
                )
            request.state.identity = identity
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Request-ID"] = request_id
    logger.info(
        json.dumps(
            {
                "event": "http.request",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            }
        )
    )
    return response


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})
