from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import Depends, FastAPI, HTTPException, Query, Request

from app.core.config import get_settings
from app.core.worker_auth import require_worker_token
from app.services.stt import FasterWhisperService
from app.services.system import gpu_status

settings = get_settings()
service = FasterWhisperService(
    settings.stt_model, settings.stt_device, settings.stt_compute_type, settings.stt_fallback_model
)
active_requests = 0
completed_requests = 0


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await service.load()
    await service.transcribe(bytes(16_000), 0, "auto")
    yield


app = FastAPI(title="Meeting Copilot STT Worker", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "model_loaded": service._model is not None,
        "model": service.model_name,
        "device": service.device,
        "compute_type": service.compute_type,
        "fallback_error": service.last_error,
        "queue_depth": active_requests,
        "completed_requests": completed_requests,
    }


@app.post("/v1/transcribe", dependencies=[Depends(require_worker_token)])
async def transcribe(
    request: Request,
    start_ms: int = Query(ge=0),
    language: str = Query(default="zh", max_length=20),
) -> dict[str, object]:
    global active_requests, completed_requests
    pcm = await request.body()
    if not pcm or len(pcm) > 16_000_000:
        raise HTTPException(413, "PCM payload must be between 1 byte and 16 MB")
    active_requests += 1
    started = perf_counter()
    try:
        segments = await service.transcribe(pcm, start_ms, language)
    finally:
        active_requests -= 1
        completed_requests += 1
    return {
        "latency_ms": round((perf_counter() - started) * 1000, 2),
        "real_time_factor": round((perf_counter() - started) / (len(pcm) / 32000), 4),
        "segments": [
            {
                "text": item.text,
                "start_ms": item.start_ms,
                "end_ms": item.end_ms,
                "confidence": item.confidence,
                "language": item.language,
            }
            for item in segments
        ]
    }


@app.get("/v1/gpu", dependencies=[Depends(require_worker_token)])
async def gpu() -> dict[str, object]:
    return await gpu_status()
