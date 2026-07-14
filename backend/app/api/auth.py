from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.base import AuthCredential, AuthSession
from app.db.session import get_db
from app.services.auth import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    add_audit,
    digest,
    is_remote_host,
    new_session_values,
    request_identity,
)

router = APIRouter()
hasher = PasswordHasher()


class Credentials(BaseModel):
    username: str = Field(default="admin", min_length=3, max_length=100)
    password: str = Field(min_length=12, max_length=200)


def _set_session_cookies(response: Response, token: str, csrf: str, max_age: int) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        secure=True,
        httponly=True,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        max_age=max_age,
        secure=True,
        httponly=False,
        samesite="strict",
        path="/",
    )


async def _create_session(
    db: AsyncSession, credential: AuthCredential, settings: Settings, response: Response
) -> None:
    token, token_hash, csrf, csrf_hash = new_session_values()
    seconds = settings.auth_session_hours * 3600
    db.add(
        AuthSession(
            token_hash=token_hash,
            credential_id=credential.id,
            csrf_hash=csrf_hash,
            expires_at=datetime.now(UTC) + timedelta(seconds=seconds),
        )
    )
    _set_session_cookies(response, token, csrf, seconds)


@router.get("/auth/status")
async def auth_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    configured = bool(await db.scalar(select(func.count()).select_from(AuthCredential)))
    identity = await request_identity(request, db)
    return {
        "configured": configured,
        "authentication_required": settings.remote_auth_required
        and is_remote_host(request.url.hostname),
        "authenticated": identity is not None,
        "username": identity.username if identity else None,
        "role": identity.role if identity else None,
    }


@router.post("/auth/bootstrap", status_code=201)
async def bootstrap(
    payload: Credentials,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    if is_remote_host(request.url.hostname):
        raise HTTPException(403, "Initial administrator setup is only allowed from localhost")
    if await db.scalar(select(func.count()).select_from(AuthCredential)):
        raise HTTPException(409, "Administrator credentials are already configured")
    credential = AuthCredential(
        username=payload.username,
        password_hash=hasher.hash(payload.password),
        role="admin",
    )
    db.add(credential)
    await db.flush()
    await _create_session(db, credential, settings, response)
    add_audit(db, payload.username, "auth.bootstrap", "auth_credential", credential.id)
    await db.commit()
    return {"authenticated": True, "username": payload.username, "role": "admin"}


@router.post("/auth/login")
async def login(
    payload: Credentials,
    response: Response,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    credential = await db.scalar(
        select(AuthCredential).where(AuthCredential.username == payload.username)
    )
    if not credential:
        raise HTTPException(401, "Invalid username or password")
    try:
        hasher.verify(credential.password_hash, payload.password)
    except VerifyMismatchError as exc:
        raise HTTPException(401, "Invalid username or password") from exc
    await db.execute(delete(AuthSession).where(AuthSession.expires_at <= datetime.now(UTC)))
    await _create_session(db, credential, settings, response)
    add_audit(db, credential.username, "auth.login", "auth_session")
    await db.commit()
    return {"authenticated": True, "username": credential.username, "role": credential.role}


@router.post("/auth/logout")
async def logout(
    request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> dict[str, bool]:
    identity = await request_identity(request, db)
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        session = await db.get(AuthSession, digest(token))
        if session:
            await db.delete(session)
    if identity:
        add_audit(db, identity.username, "auth.logout", "auth_session")
    await db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/", secure=True, samesite="strict")
    response.delete_cookie(CSRF_COOKIE, path="/", secure=True, samesite="strict")
    return {"logged_out": True}
