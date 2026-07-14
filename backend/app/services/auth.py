import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import Request, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.base import AuditEvent, AuthCredential, AuthSession

SESSION_COOKIE = "mc_session"
CSRF_COOKIE = "mc_csrf"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "test", "testserver"}


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def is_remote_host(host: str | None) -> bool:
    normalized = (host or "").strip().strip("[]").lower()
    return normalized not in LOCAL_HOSTS


def remote_auth_applies(host: str | None, settings: Settings) -> bool:
    return settings.remote_auth_required and is_remote_host(host)


@dataclass(frozen=True)
class Identity:
    credential_id: str
    username: str
    role: str
    csrf_hash: str


async def authenticate_token(
    db: AsyncSession, token: str | None
) -> Identity | None:
    if not token:
        return None
    session = await db.get(AuthSession, digest(token))
    if not session:
        return None
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        await db.delete(session)
        await db.commit()
        return None
    credential = await db.get(AuthCredential, session.credential_id)
    if not credential:
        return None
    session.last_seen_at = datetime.now(UTC)
    return Identity(credential.id, credential.username, credential.role, session.csrf_hash)


async def request_identity(request: Request, db: AsyncSession) -> Identity | None:
    return await authenticate_token(db, request.cookies.get(SESSION_COOKIE))


async def websocket_identity(websocket: WebSocket, db: AsyncSession) -> Identity | None:
    return await authenticate_token(db, websocket.cookies.get(SESSION_COOKIE))


def new_session_values() -> tuple[str, str, str, str]:
    token = secrets.token_urlsafe(48)
    csrf = secrets.token_urlsafe(32)
    return token, digest(token), csrf, digest(csrf)


def verify_csrf(identity: Identity, provided: str | None) -> bool:
    if not provided:
        return False
    return secrets.compare_digest(identity.csrf_hash, digest(provided))


def add_audit(
    db: AsyncSession,
    actor: str,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: dict[str, object] | None = None,
) -> None:
    db.add(
        AuditEvent(
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details_json=details or {},
        )
    )
