from datetime import UTC, datetime, timedelta

from app.db.base import Meeting, TranscriptSegment
from app.db.session import SessionLocal
from app.schemas.meeting import EngineOutput
from app.services.engine import apply_state_patch


async def _project_and_meeting(client):
    project = (
        await client.post(
            "/api/projects",
            json={
                "name": "Durable knowledge",
                "description": "Milestone 8",
                "default_language": "en",
            },
        )
    ).json()
    meeting_response = await client.post(
        "/api/meetings",
        json={
            "project_id": project["id"],
            "title": "Architecture council",
            "goal": "Select the durable queue",
            "privacy_acknowledged": True,
        },
    )
    assert meeting_response.status_code == 201
    return project, meeting_response.json()


async def test_immutable_decision_history_and_filters(client):
    project, meeting = await _project_and_meeting(client)
    created_response = await client.post(
        "/api/decisions",
        json={
            "meeting_id": meeting["id"],
            "project_id": project["id"],
            "title": "Use Redis for distributed locks",
            "description": "The Codex worker lock is shared through Redis.",
            "owner": "Platform",
            "status": "proposed",
            "confidence": 0.9,
        },
    )
    assert created_response.status_code == 201
    original = created_response.json()

    confirmed = await client.post(f'/api/decisions/{original["id"]}/confirm')
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"

    replacement_response = await client.post(
        f'/api/decisions/{original["id"]}/supersede',
        json={
            "title": "Use Redis with an owner-token lock",
            "description": "Release locks with an atomic compare-and-delete operation.",
            "owner": "Platform",
            "status": "confirmed",
            "confidence": 1,
        },
    )
    assert replacement_response.status_code == 201
    replacement = replacement_response.json()
    assert replacement["version"] == 2
    assert replacement["supersedes_id"] == original["id"]
    historical = (await client.get(f'/api/decisions/{original["id"]}')).json()
    assert historical["status"] == "superseded"
    assert historical["superseded_by_id"] == replacement["id"]

    filtered = await client.get(
        "/api/decisions",
        params={"project_id": project["id"], "status": "confirmed", "q": "owner-token"},
    )
    assert filtered.status_code == 200
    assert [row["id"] for row in filtered.json()] == [replacement["id"]]


async def test_action_tracker_crud_and_linked_decision(client):
    project, meeting = await _project_and_meeting(client)
    decision = (
        await client.post(
            "/api/decisions",
            json={
                "meeting_id": meeting["id"],
                "title": "Adopt PostgreSQL in Compose",
                "status": "confirmed",
            },
        )
    ).json()
    due = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    response = await client.post(
        "/api/actions",
        json={
            "meeting_id": meeting["id"],
            "project_id": project["id"],
            "title": "Add database backups",
            "description": "Document restore verification.",
            "owner": "Operations",
            "due_at": due,
            "priority": "high",
            "status": "open",
            "linked_decision_id": decision["id"],
        },
    )
    assert response.status_code == 201
    action = response.json()
    assert action["linked_decision_id"] == decision["id"]

    action["status"] = "completed"
    action["evidence_segment_ids"] = action.pop("evidence_segment_ids_json")
    action.pop("id")
    action.pop("source_suggestion_id")
    action.pop("created_at")
    action.pop("updated_at")
    updated = await client.put(f'/api/actions/{response.json()["id"]}', json=action)
    assert updated.status_code == 200
    assert updated.json()["status"] == "completed"
    assert len((await client.get("/api/actions", params={"status": "completed"})).json()) == 1

    deleted = await client.delete(f'/api/actions/{response.json()["id"]}')
    assert deleted.status_code == 204
    assert (await client.get(f'/api/actions/{response.json()["id"]}')).status_code == 404


async def test_knowledge_document_and_cross_source_search(client):
    project, meeting = await _project_and_meeting(client)
    document_response = await client.post(
        "/api/knowledge/documents",
        json={
            "project_id": project["id"],
            "source_type": "uploaded",
            "title": "Runbook",
            "content": "Rotate the PostgreSQL backup and verify the checksum every day.",
            "language": "en",
            "metadata": {"owner": "Operations"},
        },
    )
    assert document_response.status_code == 201
    document = document_response.json()
    assert document["metadata_json"] == {"owner": "Operations"}

    await client.post(
        "/api/actions",
        json={
            "meeting_id": meeting["id"],
            "title": "Verify backup checksum",
            "description": "Run the restore drill.",
            "priority": "urgent",
        },
    )
    results = await client.get(
        "/api/knowledge/search", params={"project_id": project["id"], "q": "checksum"}
    )
    assert results.status_code == 200
    assert {row["source_type"] for row in results.json()} == {"document", "action"}

    by_source = await client.get(
        "/api/knowledge/search",
        params={"project_id": project["id"], "q": "checksum", "source_type": "document"},
    )
    assert [row["id"] for row in by_source.json()] == [document["id"]]
    assert (await client.get(f'/api/knowledge/documents/{document["id"]}')).status_code == 200
    assert (await client.delete(f'/api/knowledge/documents/{document["id"]}')).status_code == 204


async def test_codex_translation_preserves_original_and_applies_glossary(client):
    project, meeting_data = await _project_and_meeting(client)
    await client.post(
        f'/api/projects/{project["id"]}/glossary',
        json={
            "term": "Codex",
            "language": "en",
            "preferred_spelling": "Codex CLI",
            "translation": "程式助理",
            "do_not_translate": True,
        },
    )
    async with SessionLocal() as db:
        segment = TranscriptSegment(
            meeting_id=meeting_data["id"],
            sequence=1,
            language="en",
            start_ms=0,
            end_ms=1000,
            text="Use Codex for reasoning.",
            confidence=1,
        )
        db.add(segment)
        await db.flush()
        meeting = await db.get(Meeting, meeting_data["id"])
        assert meeting is not None
        result = EngineOutput.model_validate(
            {
                "should_suggest": False,
                "confidence": 1,
                "category": "no_material_value",
                "suggestion": "",
                "reason": "translation only",
                "follow_up_question": None,
                "evidence_segment_ids": [],
                "state_patch": {},
                "translations": [
                    {
                        "segment_id": segment.id,
                        "language": "zh-TW",
                        "text": "使用程式助理進行推理。",
                    }
                ],
            }
        )
        await apply_state_patch(db, meeting, result)
        await db.commit()
        await db.refresh(segment)
        assert segment.text == "Use Codex for reasoning."
        assert segment.translated_language == "zh-TW"
        assert segment.translated_text == "使用Codex CLI進行推理。"
