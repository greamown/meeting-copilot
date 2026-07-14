async def test_project_glossary_memory_and_meeting_workflow(client):
    project_response = await client.post(
        "/api/projects",
        json={
            "name": "Meeting Copilot",
            "description": "Local-first meeting intelligence",
            "goals": "Preserve decisions",
            "non_goals": "Cloud audio storage",
            "default_language": "zh-TW",
        },
    )
    assert project_response.status_code == 201
    project = project_response.json()

    glossary_response = await client.post(
        f'/api/projects/{project["id"]}/glossary',
        json={
            "term": "Codex",
            "language": "en",
            "preferred_spelling": "Codex CLI",
            "translation": "Codex CLI",
            "description": "The only reasoning engine",
            "aliases": ["codex"],
            "do_not_translate": True,
        },
    )
    assert glossary_response.status_code == 201
    assert glossary_response.json()["aliases"] == ["codex"]
    duplicate = await client.post(
        f'/api/projects/{project["id"]}/glossary', json=glossary_response.json()
    )
    assert duplicate.status_code == 409

    memory_response = await client.post(
        f'/api/projects/{project["id"]}/memory',
        json={
            "category": "security_constraints",
            "title": "No credential persistence",
            "content": "Never store Codex credentials in the application database.",
            "confidence": 1,
            "status": "active",
        },
    )
    assert memory_response.status_code == 201
    memory = memory_response.json()
    memory["content"] += " Use a dedicated Docker volume."
    updated = await client.put(f'/api/project-memory/{memory["id"]}', json=memory)
    assert updated.status_code == 200
    assert updated.json()["version"] == 2

    meeting_response = await client.post(
        "/api/meetings",
        json={
            "project_id": project["id"],
            "title": "Architecture review",
            "goal": "Confirm project boundaries",
            "privacy_acknowledged": True,
        },
    )
    assert meeting_response.status_code == 201
    assert meeting_response.json()["project_id"] == project["id"]

    detail = await client.get(f'/api/projects/{project["id"]}')
    assert detail.status_code == 200
    assert detail.json()["meeting_count"] == 1
    assert detail.json()["memory_count"] == 1
    assert detail.json()["glossary_count"] == 1

    assert len((await client.get(f'/api/projects/{project["id"]}/memory')).json()) == 1
    assert len((await client.get(f'/api/projects/{project["id"]}/glossary')).json()) == 1


async def test_meeting_rejects_unknown_project(client):
    response = await client.post(
        "/api/meetings",
        json={
            "project_id": "00000000-0000-0000-0000-000000000000",
            "title": "Invalid association",
            "privacy_acknowledged": True,
        },
    )
    assert response.status_code == 422
