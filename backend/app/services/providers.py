from time import perf_counter
from typing import Any

import httpx

from app.db.base import ModelProvider
from app.services.system import codex_status
from app.core.config import Settings


async def test_provider(provider: ModelProvider, settings: Settings) -> dict[str, Any]:
    started = perf_counter()
    if provider.provider_type == "codex_cli":
        result = await codex_status(settings)
        healthy = bool(result["installed"])
        detail = "Codex CLI available" if healthy else result.get("error", "Unavailable")
    elif provider.provider_type in ("local_faster_whisper", "browser_speech_synthesis"):
        healthy, detail = True, "Local adapter configured"
    elif provider.base_url:
        try:
            async with httpx.AsyncClient(timeout=provider.timeout_seconds) as client:
                response = await client.get(str(provider.base_url).rstrip("/") + "/models")
            healthy, detail = response.status_code < 500, f"HTTP {response.status_code}"
        except httpx.HTTPError as exc:
            healthy, detail = False, type(exc).__name__
    else:
        healthy, detail = False, "Base URL required"
    return {"healthy": healthy, "latency_ms": round((perf_counter() - started) * 1000), "detail": detail}
