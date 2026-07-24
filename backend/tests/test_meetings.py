async def test_meeting_lifecycle(client):
    payload = {
        "title": "Architecture sync",
        "goal": "Choose queue semantics",
        "privacy_acknowledged": True,
        "participants": ["Alice"],
    }
    created = await client.post("/api/meetings", json=payload)
    assert created.status_code == 201
    meeting_id = created.json()["id"]
    assert (await client.post(f"/api/meetings/{meeting_id}/start")).json()["meeting"][
        "status"
    ] == "active"
    assert (await client.post(f"/api/meetings/{meeting_id}/pause")).json()["meeting"][
        "status"
    ] == "paused"
    assert (await client.post(f"/api/meetings/{meeting_id}/resume")).json()["meeting"][
        "status"
    ] == "active"
    assert (await client.post(f"/api/meetings/{meeting_id}/end")).json()["meeting"][
        "status"
    ] == "ended"


async def test_meeting_create_is_idempotent(client):
    payload = {
        "title": "Retry-safe meeting",
        "goal": "Verify idempotency",
        "language": "en",
        "privacy_acknowledged": True,
    }
    headers = {"X-Idempotency-Key": "meeting-create-test-key"}
    first = await client.post("/api/meetings", json=payload, headers=headers)
    second = await client.post("/api/meetings", json=payload, headers=headers)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    conflict = await client.post(
        "/api/meetings",
        json={**payload, "title": "Different meeting"},
        headers=headers,
    )
    assert conflict.status_code == 409


async def test_meeting_analytics_counts_from_database(client):
    meeting_id = (
        await client.post(
            "/api/meetings",
            json={"title": "Analytics", "goal": "Count things", "privacy_acknowledged": True},
        )
    ).json()["id"]
    await client.post(f"/api/meetings/{meeting_id}/start")
    await client.post(
        "/api/decisions",
        json={"meeting_id": meeting_id, "title": "Ship it", "description": "Agreed"},
    )
    await client.post(
        "/api/actions",
        json={
            "meeting_id": meeting_id,
            "title": "Write the migration",
            "owner": "Alice",
            "due_at": "2020-01-01T00:00:00Z",
        },
    )
    await client.post(
        "/api/actions", json={"meeting_id": meeting_id, "title": "Unassigned follow-up"}
    )
    await client.post(f"/api/meetings/{meeting_id}/end")

    analytics = (await client.get(f"/api/meetings/{meeting_id}/analytics")).json()
    assert analytics["duration_source"] == "meeting_timestamps"
    assert analytics["decisions"]["total"] == 1
    assert analytics["actions"] == {
        "total": 2,
        "with_owner": 1,
        "with_due_date": 1,
        "completed": 0,
        "overdue": 1,
        "average_completion_hours": None,
    }
    assert analytics["effectiveness"]["actions_with_owner_ratio"] == 0.5
    assert analytics["transcript"]["segments"] == 0


async def test_meeting_audio_download_requires_stored_audio(client):
    meeting_id = (
        await client.post(
            "/api/meetings",
            json={"title": "No audio", "privacy_acknowledged": True},
        )
    ).json()["id"]
    assert (await client.get(f"/api/meetings/{meeting_id}/audio")).status_code == 404


async def test_provider_registry_masks_secret(client, monkeypatch):
    monkeypatch.setenv("TEST_PROVIDER_KEY", "do-not-return")
    payload = {
        "id": "test-stt",
        "name": "Test STT",
        "role": "stt",
        "provider_type": "openai_compatible_stt",
        "base_url": "http://localhost:9999",
        "secret_ref": "TEST_PROVIDER_KEY",
        "model": "whisper",
    }
    response = await client.post("/api/providers", json=payload)
    assert response.status_code == 201
    assert response.json()["secret_ref"] == "TEST_PROVIDER_KEY"
    assert "do-not-return" not in response.text
