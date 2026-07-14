from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, HttpUrl


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str


class ProviderBase(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{2,63}$")
    name: str = Field(min_length=1, max_length=100)
    role: Literal["reasoning", "stt", "tts", "embedding", "reranker"]
    provider_type: Literal["codex_cli", "local_faster_whisper", "openai_compatible_stt", "browser_speech_synthesis", "openai_compatible_tts", "openai_compatible_embedding", "custom_http"]
    base_url: HttpUrl | None = None
    secret_ref: str | None = Field(default=None, max_length=200)
    model: str | None = Field(default=None, max_length=100)
    enabled: bool = True
    timeout_seconds: int = Field(default=60, ge=1, le=600)
    max_retries: int = Field(default=2, ge=0, le=5)
    extra: dict[str, Any] = Field(default_factory=dict)


class ProviderRead(ProviderBase):
    model_config = ConfigDict(from_attributes=True)
    is_default: bool
    health_status: str
    last_latency_ms: int | None
    created_at: datetime
    updated_at: datetime
    extra: dict[str, Any] = Field(default_factory=dict, validation_alias=AliasChoices("extra", "extra_json"))


class EventEnvelope(BaseModel):
    event_id: str
    meeting_id: str
    type: str
    created_at: datetime
    source: str
    sequence: int
    payload: dict[str, Any]
