import asyncio
from pathlib import Path
from typing import Any

import httpx

from app.core.config import Settings
from app.db.base import CodexRun, ModelProvider
from app.services.engine import manager
from app.services.providers import test_provider as check_provider
from app.services.stt import RemoteSTTService
from app.services.system import codex_status, gpu_status
from app.workers.engine_api import clean_cli_output, clean_login_line


class FakeClient:
    response: httpx.Response
    last_request: dict[str, Any] = {}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> "FakeClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        type(self).last_request = {"method": "POST", "url": url, **kwargs}
        return self.response

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        type(self).last_request = {"method": "GET", "url": url, **kwargs}
        return self.response


def response(status: int, payload: dict[str, Any]) -> httpx.Response:
    return httpx.Response(status, json=payload, request=httpx.Request("GET", "http://worker"))


def settings(tmp_path: Path, **values: Any) -> Settings:
    token = tmp_path / "token"
    token.write_text("worker-secret")
    return Settings(worker_token_file=token, **values)


def test_codex_login_output_hides_path_warning_but_keeps_device_flow():
    assert clean_login_line("WARNING: could not create PATH aliases: denied") == ""
    assert clean_login_line("\x1b[90mOpen \x1b[94mhttps://auth.openai.com/codex/device\x1b[0m") == (
        "Open https://auth.openai.com/codex/device"
    )
    assert (
        clean_cli_output("WARNING: could not create PATH aliases: denied\nLogged in")
        == "Logged in"
    )


def test_remote_stt_uses_authenticated_worker(monkeypatch, tmp_path: Path):
    FakeClient.response = response(
        200, {"segments": [{"text": "hello", "start_ms": 10, "end_ms": 500, "confidence": 0.9}]}
    )
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    service = RemoteSTTService(settings(tmp_path, stt_worker_url="http://stt-worker:8001"))
    rows = asyncio.run(service.transcribe(b"pcm", 10, "en"))
    assert rows[0].text == "hello"
    assert FakeClient.last_request["headers"]["X-Worker-Token"] == "worker-secret"


def test_remote_codex_returns_validated_result(monkeypatch, tmp_path: Path):
    result = {
        "should_suggest": False,
        "confidence": 0,
        "category": "no_material_value",
        "suggestion": "",
        "reason": "none",
        "follow_up_question": None,
        "evidence_segment_ids": [],
        "state_patch": {
            "current_topic": None,
            "add_decisions": [],
            "add_open_questions": [],
            "add_risks": [],
            "add_action_items": [],
            "add_parking_lot": [],
        },
    }
    FakeClient.response = response(200, {"result": result, "retry_count": 1, "duration_ms": 25})
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    run = CodexRun(
        id="run-1",
        meeting_id="meeting-1",
        job_type="manual",
        trigger="manual",
        status="running",
        request_json={"recent_transcript": []},
    )
    parsed = asyncio.run(
        manager._remote_execute(
            run, settings(tmp_path, cli_worker_url="http://codex-worker:8002")
        )
    )
    assert parsed.should_suggest is False
    assert run.retry_count == 1
    assert FakeClient.last_request["json"]["run_id"] == "run-1"


def test_remote_health_proxies_worker_status(monkeypatch, tmp_path: Path):
    FakeClient.response = response(
        200,
        {"installed": True, "authenticated": True, "version": "codex 1", "provider": "codex_cli"},
    )
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    status = asyncio.run(
        codex_status(settings(tmp_path, cli_worker_url="http://codex-worker:8002"))
    )
    assert status["authenticated"] is True
    FakeClient.response = response(200, {"available": True, "gpus": [{"name": "A6000"}]})
    gpu = asyncio.run(gpu_status(settings(tmp_path, stt_worker_url="http://stt-worker:8001")))
    assert gpu["gpus"][0]["name"] == "A6000"


def test_provider_health_uses_tts_worker_health_endpoint(monkeypatch, tmp_path: Path):
    FakeClient.response = response(200, {"status": "ok"})
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    provider = ModelProvider(
        id="local-tts",
        name="Local TTS",
        role="tts",
        provider_type="openai_compatible_tts",
        base_url="http://tts-worker:8003/v1",
    )
    result = asyncio.run(
        check_provider(provider, settings(tmp_path, tts_worker_url="http://tts-worker:8003"))
    )
    assert result["healthy"] is True
    assert FakeClient.last_request["url"] == "http://tts-worker:8003/health"


def test_generic_provider_health_rejects_not_found(monkeypatch, tmp_path: Path):
    FakeClient.response = response(404, {"detail": "not found"})
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    provider = ModelProvider(
        id="remote-tts",
        name="Remote TTS",
        role="tts",
        provider_type="openai_compatible_tts",
        base_url="https://provider.invalid/v1",
    )
    result = asyncio.run(check_provider(provider, settings(tmp_path)))
    assert result["healthy"] is False
