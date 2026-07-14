async def test_meeting_lifecycle(client):
    payload = {"title":"Architecture sync","goal":"Choose queue semantics","privacy_acknowledged":True,"participants":["Alice"]}
    created = await client.post("/api/meetings", json=payload)
    assert created.status_code == 201
    meeting_id = created.json()["id"]
    assert (await client.post(f"/api/meetings/{meeting_id}/start")).json()["meeting"]["status"] == "active"
    assert (await client.post(f"/api/meetings/{meeting_id}/pause")).json()["meeting"]["status"] == "paused"
    assert (await client.post(f"/api/meetings/{meeting_id}/resume")).json()["meeting"]["status"] == "active"
    assert (await client.post(f"/api/meetings/{meeting_id}/end")).json()["meeting"]["status"] == "ended"


async def test_provider_registry_masks_secret(client, monkeypatch):
    monkeypatch.setenv("TEST_PROVIDER_KEY", "do-not-return")
    payload = {"id":"test-stt","name":"Test STT","role":"stt","provider_type":"openai_compatible_stt","base_url":"http://localhost:9999","secret_ref":"TEST_PROVIDER_KEY","model":"whisper"}
    response = await client.post("/api/providers", json=payload)
    assert response.status_code == 201
    assert response.json()["secret_ref"] == "TEST_PROVIDER_KEY"
    assert "do-not-return" not in response.text
