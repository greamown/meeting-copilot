from contextlib import asynccontextmanager
import json
import logging
from pathlib import Path
from time import perf_counter
from typing import AsyncIterator
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import update

from app.api.system import router as system_router
from app.api.providers import router as providers_router
from app.api.meetings import router as meetings_router
from app.api.diagnostics import router as diagnostics_router
from app.core.config import get_settings
from app.db.base import Base, CodexRun, Meeting, ModelProvider
from app.db.session import SessionLocal, engine

settings = get_settings()
logger = logging.getLogger("meeting_copilot")
logging.basicConfig(level=logging.INFO, format="%(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings.runtime_dir.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        await session.execute(update(Meeting).where(Meeting.status.in_(["active", "paused"])).values(status="interrupted"))
        await session.execute(update(CodexRun).where(CodexRun.status.in_(["queued", "preparing_context", "running", "validating"])).values(status="failed", sanitized_stderr="Worker restarted"))
        defaults = [
            {"id": "codex-local", "name": "Codex CLI", "role": "reasoning", "provider_type": "codex_cli", "model": settings.codex_model, "is_default": True, "extra_json": {"sandbox": "read-only", "approval_policy": "never", "network_access": False, "repository_access": False}},
            {"id": "local-stt-primary", "name": "Local Whisper", "role": "stt", "provider_type": "local_faster_whisper", "model": settings.stt_model, "is_default": True, "extra_json": {"device": settings.stt_device, "compute_type": settings.stt_compute_type, "language": "zh", "vad_filter": True}},
            {"id": "browser-tts", "name": "Browser Speech", "role": "tts", "provider_type": "browser_speech_synthesis", "model": None, "is_default": True, "extra_json": {}},
        ]
        for values in defaults:
            if not await session.get(ModelProvider, values["id"]): session.add(ModelProvider(**values))
        await session.commit()
    yield
    await engine.dispose()


app = FastAPI(title="Meeting Copilot API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=False, allow_methods=["*"], allow_headers=["Content-Type", "X-Request-ID", "X-Idempotency-Key"])
app.include_router(system_router, prefix="/api", tags=["system"])
app.include_router(providers_router, prefix="/api", tags=["providers"])
app.include_router(meetings_router, prefix="/api", tags=["meetings"])
app.include_router(diagnostics_router, prefix="/api", tags=["diagnostics"])


@app.middleware("http")
async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = request.headers.get("X-Request-ID", str(uuid4()))[:100]
    started = perf_counter()
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Request-ID"] = request_id
    logger.info(json.dumps({"event": "http.request", "request_id": request_id, "method": request.method, "path": request.url.path, "status": response.status_code, "duration_ms": round((perf_counter() - started) * 1000, 2)}))
    return response


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})
