import asyncio
import tempfile
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

from app.core.worker_auth import require_worker_token

app = FastAPI(title="Meeting Copilot Optional TTS Worker")


class SpeechRequest(BaseModel):
    model: str | None = None
    input: str = Field(min_length=1, max_length=5000)
    voice: Literal["zh", "zh-yue", "en", "en-us", "ja"] = "zh"
    response_format: Literal["wav"] = "wav"
    speed: float = Field(default=1, ge=0.5, le=2)
    volume: float = Field(default=1, ge=0, le=1)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "engine": "espeak-ng"}


@app.post("/v1/audio/speech", dependencies=[Depends(require_worker_token)])
async def speech(payload: SpeechRequest) -> Response:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
        output = Path(handle.name)
    try:
        process = await asyncio.create_subprocess_exec(
            "espeak-ng",
            "-v",
            payload.voice,
            "-s",
            str(round(175 * payload.speed)),
            "-a",
            str(round(200 * payload.volume)),
            "-w",
            str(output),
            payload.input,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(process.communicate(), 30)
        if process.returncode != 0:
            raise HTTPException(502, f"TTS engine failed: {stderr.decode(errors='replace')[:300]}")
        return Response(output.read_bytes(), media_type="audio/wav")
    finally:
        output.unlink(missing_ok=True)
