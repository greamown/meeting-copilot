import os
from unittest.mock import AsyncMock

os.environ["MC_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from fastapi.testclient import TestClient

from app.main import app
from app.core.config import get_settings
from app.services.stt import FasterWhisperService, Transcription


async def settings_override():
    return get_settings()


app.dependency_overrides[get_settings] = settings_override


def test_audio_websocket_persists_transcript(monkeypatch):
    monkeypatch.setattr(FasterWhisperService, "transcribe", AsyncMock(return_value=[Transcription("測試逐字稿", 0, 1000, 0.9)]))
    with TestClient(app) as client:
        meeting = client.post("/api/meetings", json={"title": "Audio", "privacy_acknowledged": True}).json()
        client.post(f"/api/meetings/{meeting['id']}/start")
        with client.websocket_connect(f"/api/meetings/{meeting['id']}/audio") as socket:
            for sequence in range(4):
                frame = sequence.to_bytes(8, "little") + bytes(50_000)
                socket.send_bytes(frame)
                assert socket.receive_json()["sequence"] == sequence
        detail = client.get(f"/api/meetings/{meeting['id']}").json()
        assert detail["transcripts"][0]["text"] == "測試逐字稿"
        assert detail["transcripts"][0]["confidence"] == 0.9
