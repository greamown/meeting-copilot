import os
from unittest.mock import AsyncMock

os.environ["MC_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.stt import FasterWhisperService, Transcription


async def settings_override():
    return get_settings()


app.dependency_overrides[get_settings] = settings_override


def test_audio_websocket_persists_transcript_and_enforces_glossary(monkeypatch):
    monkeypatch.setattr(
        FasterWhisperService,
        "transcribe",
        AsyncMock(return_value=[Transcription("使用 codecks", 0, 1000, 0.9, "zh")]),
    )
    with TestClient(app) as client:
        project = client.post(
            "/api/projects", json={"name": "Audio glossary", "default_language": "zh-TW"}
        ).json()
        client.post(
            f"/api/projects/{project['id']}/glossary",
            json={
                "term": "Codex",
                "language": "en",
                "preferred_spelling": "Codex CLI",
                "aliases": ["codecks"],
                "do_not_translate": True,
            },
        )
        meeting = client.post(
            "/api/meetings",
            json={
                "project_id": project["id"],
                "title": "Audio",
                "privacy_acknowledged": True,
                "secondary_language": "en",
            },
        ).json()
        client.post(f"/api/meetings/{meeting['id']}/start")
        with client.websocket_connect(f"/api/meetings/{meeting['id']}/audio") as socket:
            for sequence in range(4):
                frame = sequence.to_bytes(8, "little") + bytes(50_000)
                socket.send_bytes(frame)
                assert socket.receive_json()["sequence"] == sequence
        detail = client.get(f"/api/meetings/{meeting['id']}").json()
        assert detail["transcripts"][0]["text"] == "使用 Codex CLI"
        assert detail["transcripts"][0]["confidence"] == 0.9
        assert detail["transcripts"][0]["language"] == "zh"
        assert FasterWhisperService.transcribe.await_args.args[2] == "auto"
        event_types = {
            event["type"]
            for event in client.get("/api/diagnostics").json()["events"]
            if event["meeting_id"] == meeting["id"]
        }
        assert {"transcript.partial", "transcript.final"}.issubset(event_types)


def test_audio_websocket_reports_lost_chunk():
    with TestClient(app) as client:
        meeting = client.post(
            "/api/meetings", json={"title": "Sequence gap", "privacy_acknowledged": True}
        ).json()
        client.post(f"/api/meetings/{meeting['id']}/start")
        with client.websocket_connect(f"/api/meetings/{meeting['id']}/audio") as socket:
            socket.send_bytes((2).to_bytes(8, "little") + bytes(1_000))
            assert socket.receive_json()["sequence"] == 2
        events = client.get("/api/diagnostics").json()["events"]
        dropped = next(
            event
            for event in events
            if event["meeting_id"] == meeting["id"] and event["type"] == "audio.chunk.dropped"
        )
        assert dropped["payload"] == {"expected": 0, "received": 2}
