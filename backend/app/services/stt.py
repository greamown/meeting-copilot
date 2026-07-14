import asyncio
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Transcription:
    text: str
    start_ms: int
    end_ms: int
    confidence: float | None


class FasterWhisperService:
    """Lazy, reusable faster-whisper model with explicit CUDA fallback policy."""

    def __init__(self, model: str, device: str, compute_type: str, fallback_model: str | None = None) -> None:
        self.model_name, self.device, self.compute_type = model, device, compute_type
        self.fallback_model = fallback_model
        self._model: Any = None
        self._lock = asyncio.Lock()
        self.last_error: str | None = None

    async def load(self) -> None:
        if self._model is not None:
            return
        async with self._lock:
            if self._model is not None:
                return
            try:
                from faster_whisper import WhisperModel
                self._model = await asyncio.to_thread(WhisperModel, self.model_name, device=self.device, compute_type=self.compute_type)
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
                if self.device == "cuda" and self.fallback_model:
                    from faster_whisper import WhisperModel
                    self._model = await asyncio.to_thread(WhisperModel, self.fallback_model, device="cpu", compute_type="int8")
                    self.device, self.compute_type = "cpu", "int8"
                else:
                    raise

    async def transcribe(self, pcm16: bytes, start_ms: int, language: str = "zh") -> list[Transcription]:
        await self.load()
        import numpy as np
        audio = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0
        segments, _ = await asyncio.to_thread(self._model.transcribe, audio, language=language, vad_filter=True, beam_size=5)
        rows = list(segments)
        return [Transcription(segment.text.strip(), start_ms + int(segment.start * 1000), start_ms + int(segment.end * 1000), None if segment.avg_logprob is None else max(0.0, min(1.0, 1 + segment.avg_logprob))) for segment in rows if segment.text.strip()]
