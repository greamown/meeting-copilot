from unittest.mock import AsyncMock, patch


async def test_health(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_gpu_absent_is_safe(client):
    with patch("app.services.system.shutil.which", return_value=None):
        response = await client.get("/api/system/gpu")
    assert response.status_code == 200
    assert response.json()["available"] is False


async def test_codex_status_never_exposes_token(client):
    with patch("app.services.system.shutil.which", return_value="/usr/bin/codex"), patch(
        "app.services.system.run_command", new=AsyncMock(side_effect=[(0, "codex 1.0", ""), (1, "", "Authorization: Bearer secret-token")])
    ):
        response = await client.get("/api/codex/status")
    assert "secret-token" not in response.text
    assert "[REDACTED]" in response.text
