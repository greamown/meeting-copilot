import secrets

from fastapi import Header, HTTPException

from app.core.config import get_settings


def worker_headers() -> dict[str, str]:
    token = get_settings().worker_token()
    if not token:
        raise RuntimeError("Worker token is not configured")
    return {"X-Worker-Token": token}


async def require_worker_token(x_worker_token: str = Header(default="")) -> None:
    expected = get_settings().worker_token()
    if not expected or not secrets.compare_digest(x_worker_token, expected):
        raise HTTPException(status_code=401, detail="Invalid worker token")
