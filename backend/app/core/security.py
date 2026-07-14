import re
from pathlib import Path
from typing import Any

SECRET_PATTERNS = [
    re.compile(r"(?i)(authorization\s*[:=]\s*(?:bearer\s+)?)[^\s,;]+"),
    re.compile(r"(?i)((?:api[_-]?key|access[_-]?token|refresh[_-]?token|cookie)\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"\b(?:sk|sess)-[A-Za-z0-9_-]{12,}\b"),
]


def redact(value: str) -> str:
    """Remove credentials from text before persistence or API output."""
    sanitized = value
    for pattern in SECRET_PATTERNS:
        sanitized = pattern.sub(lambda match: f"{match.group(1)}[REDACTED]" if match.lastindex else "[REDACTED]", sanitized)
    return sanitized[:8000]


def mask_secret_ref(value: str | None) -> str | None:
    if not value:
        return value
    return f"{value[:3]}***{value[-2:]}" if len(value) > 5 else "***"


def allowlisted_path(raw_path: str, roots: list[Path]) -> Path:
    """Resolve a repository path and ensure it is inside an explicit root."""
    path = Path(raw_path).expanduser().resolve(strict=True)
    if not any(path == root.resolve() or path.is_relative_to(root.resolve()) for root in roots):
        raise ValueError("Repository path is outside configured roots")
    return path


def scrub_mapping(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if any(token in key.lower() for token in ("key", "token", "secret", "cookie", "authorization")) else scrub_mapping(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [scrub_mapping(item) for item in value]
    return redact(value) if isinstance(value, str) else value
