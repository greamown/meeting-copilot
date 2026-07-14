import asyncio
import platform
import shutil
import sys
from pathlib import Path
from time import perf_counter
from typing import Any, cast

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import redact


async def run_command(args: list[str], timeout: float = 5) -> tuple[int, str, str]:
    try:
        process = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
        return (
            process.returncode or 0,
            stdout.decode(errors="replace"),
            redact(stderr.decode(errors="replace")),
        )
    except (TimeoutError, FileNotFoundError) as exc:
        return 127, "", redact(str(exc))


async def gpu_status(settings: Settings | None = None) -> dict[str, Any]:
    if settings and settings.stt_worker_url:
        token = settings.worker_token()
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"{settings.stt_worker_url.rstrip('/')}/v1/gpu",
                    headers={"X-Worker-Token": token},
                )
            response.raise_for_status()
            return cast(dict[str, Any], response.json())
        except httpx.HTTPError as exc:
            return {
                "available": False,
                "gpus": [],
                "error": f"STT worker unavailable: {type(exc).__name__}",
            }
    if not shutil.which("nvidia-smi"):
        return {"available": False, "gpus": [], "error": "nvidia-smi not found"}
    fields = "name,memory.total,memory.used,utilization.gpu,driver_version"
    code, stdout, stderr = await run_command(
        ["nvidia-smi", f"--query-gpu={fields}", "--format=csv,noheader,nounits"]
    )
    if code:
        return {"available": False, "gpus": [], "error": stderr or "nvidia-smi failed"}
    gpus = []
    for line in stdout.strip().splitlines():
        name, total, used, utilization, driver = [part.strip() for part in line.split(",")]
        gpus.append(
            {
                "name": name,
                "memory_total_mb": int(total),
                "memory_used_mb": int(used),
                "utilization_percent": int(utilization),
                "driver_version": driver,
            }
        )
    return {"available": bool(gpus), "gpus": gpus, "cuda_available": bool(gpus)}


async def codex_status(settings: Settings) -> dict[str, Any]:
    if settings.codex_worker_url:
        token = settings.worker_token()
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.get(
                    f"{settings.codex_worker_url.rstrip('/')}/v1/status",
                    headers={"X-Worker-Token": token},
                )
            response.raise_for_status()
            return cast(dict[str, Any], response.json())
        except httpx.HTTPError as exc:
            return {
                "installed": False,
                "authenticated": False,
                "version": None,
                "profile": settings.codex_profile,
                "model": settings.codex_model,
                "provider": "codex_cli",
                "error": f"Codex worker unavailable: {type(exc).__name__}",
            }
    path = shutil.which(settings.codex_bin)
    if not path:
        return {
            "installed": False,
            "authenticated": False,
            "version": None,
            "profile": settings.codex_profile,
            "model": settings.codex_model,
            "provider": "codex_cli",
            "error": "Codex CLI not found",
        }
    version_code, version, version_error = await run_command([path, "--version"])
    auth_code, auth_output, auth_error = await run_command([path, "login", "status"])
    return {
        "installed": version_code == 0,
        "authenticated": auth_code == 0,
        "version": version.strip() or None,
        "profile": settings.codex_profile,
        "model": settings.codex_model,
        "provider": "codex_cli",
        "error": redact(version_error or auth_error),
        "status": redact(auth_output.strip()),
    }


async def system_status(db: AsyncSession, settings: Settings) -> dict[str, Any]:
    started = perf_counter()
    await db.execute(text("SELECT 1"))
    db_latency = round((perf_counter() - started) * 1000, 2)
    disk = shutil.disk_usage(Path.cwd())
    gpu, codex = await asyncio.gather(gpu_status(settings), codex_status(settings))
    redis_status: bool | None = None
    redis_latency: float | None = None
    if settings.redis_url:
        try:
            from redis.asyncio import Redis

            redis = Redis.from_url(settings.redis_url)
            redis_started = perf_counter()
            redis_status = bool(await redis.ping())
            redis_latency = round((perf_counter() - redis_started) * 1000, 2)
            await redis.aclose()
        except Exception:
            redis_status = False
    return {
        "os": f"{platform.system()} {platform.release()}",
        "python_version": sys.version.split()[0],
        "docker_available": Path("/.dockerenv").exists() or shutil.which("docker") is not None,
        "docker_compose_available": Path("/.dockerenv").exists(),
        "nvidia_container_toolkit_available": bool(gpu.get("available")),
        "ffmpeg_available": shutil.which("ffmpeg") is not None,
        "codex": codex,
        "gpu": gpu,
        "database": {
            "healthy": True,
            "latency_ms": db_latency,
            "dialect": db.bind.dialect.name if db.bind else "unknown",
        },
        "redis": {
            "enabled": bool(settings.redis_url),
            "healthy": redis_status,
            "latency_ms": redis_latency,
        },
        "disk": {
            "free_gb": round(disk.free / 1024**3, 1),
            "total_gb": round(disk.total / 1024**3, 1),
        },
    }
