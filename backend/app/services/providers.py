from time import perf_counter
from typing import Any

import httpx

from app.core.config import Settings
from app.db.base import ModelProvider
from app.services.system import codex_status


def worker_base_url(value: str) -> str:
    return value.rstrip("/").removesuffix("/v1")


async def test_provider(provider: ModelProvider, settings: Settings) -> dict[str, Any]:
    started = perf_counter()
    if provider.provider_type == "codex_cli":
        result = await codex_status(settings)
        healthy = bool(result["installed"])
        detail = "Codex CLI available" if healthy else result.get("error", "Unavailable")
    elif provider.provider_type in ("local_faster_whisper", "browser_speech_synthesis"):
        healthy, detail = True, "Local adapter configured"
    elif (
        provider.provider_type == "openai_compatible_tts"
        and settings.tts_worker_url
        and provider.base_url
        and worker_base_url(str(provider.base_url)) == settings.tts_worker_url.rstrip("/")
    ):
        try:
            async with httpx.AsyncClient(timeout=provider.timeout_seconds) as client:
                response = await client.get(settings.tts_worker_url.rstrip("/") + "/health")
            healthy, detail = response.is_success, f"HTTP {response.status_code}"
        except httpx.HTTPError as exc:
            healthy, detail = False, type(exc).__name__
    elif provider.base_url:
        try:
            async with httpx.AsyncClient(timeout=provider.timeout_seconds) as client:
                response = await client.get(str(provider.base_url).rstrip("/") + "/models")
            healthy, detail = response.is_success, f"HTTP {response.status_code}"
        except httpx.HTTPError as exc:
            healthy, detail = False, type(exc).__name__
    else:
        healthy, detail = False, "Base URL required"
    return {
        "healthy": healthy,
        "latency_ms": round((perf_counter() - started) * 1000),
        "detail": detail,
    }
