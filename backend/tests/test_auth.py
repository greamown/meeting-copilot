import importlib

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.base import AuthCredential, AuthSession
from app.db.session import SessionLocal
from app.main import app


async def test_remote_authentication_and_csrf(client, monkeypatch):
    main_module = importlib.import_module("app.main")
    monkeypatch.setattr(main_module.settings, "remote_auth_required", True)

    password = "test-only-strong-password"
    bootstrap = await client.post(
        "/api/auth/bootstrap",
        json={"username": "admin", "password": password},
    )
    assert bootstrap.status_code == 201

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://192.0.2.10") as remote:
        assert (await remote.get("/api/projects")).status_code == 401
        assert (
            await remote.post(
                "/api/auth/bootstrap",
                json={"username": "other-admin", "password": password},
            )
        ).status_code == 403
        assert (
            await remote.post(
                "/api/auth/login",
                json={"username": "admin", "password": "incorrect-password"},
            )
        ).status_code == 401

        login = await remote.post(
            "/api/auth/login",
            json={"username": "admin", "password": password},
        )
        assert login.status_code == 200
        assert remote.cookies.get("mc_session")
        csrf = remote.cookies.get("mc_csrf")
        assert csrf
        assert "Secure" in login.headers.get_list("set-cookie")[0]

        assert (await remote.get("/api/projects")).status_code == 200
        project = {"name": "Authenticated project", "description": "", "goals": ""}
        assert (await remote.post("/api/projects", json=project)).status_code == 403
        created = await remote.post(
            "/api/projects",
            json=project,
            headers={"X-CSRF-Token": csrf},
        )
        assert created.status_code == 201

        logout = await remote.post(
            "/api/auth/logout",
            headers={"X-CSRF-Token": csrf},
        )
        assert logout.status_code == 200
        assert (await remote.get("/api/projects")).status_code == 401

    async with SessionLocal() as session:
        credential = await session.scalar(select(AuthCredential))
        assert credential is not None
        assert credential.password_hash.startswith("$argon2")
        assert password not in credential.password_hash
        sessions = list((await session.scalars(select(AuthSession))).all())
        assert len(sessions) == 1
        assert len(sessions[0].token_hash) == 64
        assert len(sessions[0].csrf_hash) == 64
