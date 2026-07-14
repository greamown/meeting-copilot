from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated process configuration. Secrets are referenced, never returned by APIs."""

    model_config = SettingsConfigDict(env_prefix="MC_", env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./runtime/meeting-copilot.db"
    host: str = "127.0.0.1"
    port: int = 8000
    allowed_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
    repository_roots: list[Path] = []
    redis_url: str | None = None
    codex_bin: str = "codex"
    codex_profile: str | None = None
    codex_model: str | None = None
    stt_model: str = "large-v3-turbo"
    stt_device: str = "cuda"
    stt_compute_type: str = "float16"
    stt_fallback_model: str | None = "medium"
    runtime_dir: Path = Path("runtime")
    secret_file: Path = Path("runtime/secrets.json.enc")
    secret_key: str | None = None
    max_audio_frame_bytes: int = 64_000
    codex_timeout_seconds: int = 180

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        return value.split(",") if isinstance(value, str) else value

    @field_validator("repository_roots", mode="before")
    @classmethod
    def split_paths(cls, value: object) -> object:
        return [Path(item) for item in value.split(",") if item] if isinstance(value, str) else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
