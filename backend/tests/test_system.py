from unittest.mock import AsyncMock, patch


async def test_health(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert (await client.get("/api/live")).status_code == 200
    assert (await client.get("/api/ready")).status_code == 200


async def test_required_metrics_are_exposed(client):
    response = await client.get("/api/metrics")
    assert response.status_code == 200
    required = {
        "active_meetings",
        "audio_chunks_received",
        "audio_chunks_dropped",
        "stt_latency_ms",
        "stt_real_time_factor",
        "stt_queue_depth",
        "codex_queue_depth",
        "codex_latency_ms",
        "codex_success_rate",
        "codex_failure_rate",
        "codex_timeout_rate",
        "suggestions_generated",
        "suggestions_accepted",
        "suggestions_ignored",
        "duplicate_suggestions_suppressed",
        "tts_latency_ms",
        "database_latency_ms",
        "redis_latency_ms",
        "websocket_connections",
        "gpu",
    }
    assert required.issubset(response.json())


async def test_gpu_absent_is_safe(client):
    with patch("app.services.system.shutil.which", return_value=None):
        response = await client.get("/api/system/gpu")
    assert response.status_code == 200
    assert response.json()["available"] is False


async def test_codex_status_never_exposes_token(client):
    with (
        patch("app.services.system.shutil.which", return_value="/usr/bin/codex"),
        patch(
            "app.services.system.run_command",
            new=AsyncMock(
                side_effect=[(0, "codex 1.0", ""), (1, "", "Authorization: Bearer secret-token")]
            ),
        ),
    ):
        response = await client.get("/api/codex/status")
    assert "secret-token" not in response.text
    assert "[REDACTED]" in response.text


async def test_language_settings_persist_and_validate(client):
    current = (await client.get("/api/settings")).json()
    current.update(
        {
            "setup_completed": True,
            "ui_language": "en",
            "meeting_input_language": "ja",
            "secondary_meeting_language": "zh-TW",
            "translation_language": "ko",
            "suggestion_output_language": "zh-CN",
            "summary_output_language": "en",
            "export_language": "original",
            "tts_language": "ja",
        }
    )
    response = await client.put("/api/settings", json=current)
    assert response.status_code == 200
    saved = (await client.get("/api/settings")).json()
    assert saved["setup_completed"] is True
    assert saved["meeting_input_language"] == "ja"
    assert saved["translation_language"] == "ko"

    invalid = {**saved, "ui_language": "invalid"}
    assert (await client.put("/api/settings", json=invalid)).status_code == 422


async def test_provider_toggle_prevents_disabled_default(client):
    providers = (await client.get("/api/providers")).json()
    provider = next(item for item in providers if item["enabled"])

    disabled = await client.post(f'/api/providers/{provider["id"]}/toggle')
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False
    assert disabled.json()["is_default"] is False
    assert (await client.post(f'/api/providers/{provider["id"]}/set-default')).status_code == 409

    restored = await client.post(f'/api/providers/{provider["id"]}/toggle')
    assert restored.status_code == 200
    assert restored.json()["enabled"] is True
