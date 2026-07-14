import asyncio
import os
import stat
import textwrap
from pathlib import Path

os.environ["MC_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.config import get_settings


async def settings_override():
    return get_settings()


app.dependency_overrides[get_settings] = settings_override


async def main() -> None:
    mock = Path("runtime/mock_codex.py").resolve()
    mock.parent.mkdir(exist_ok=True)
    mock.write_text(textwrap.dedent("""\
        #!/usr/bin/env python3
        import json, os, sys, time
        mode = os.environ.get("MOCK_CODEX_MODE", "valid")
        output = sys.argv[sys.argv.index("--output-last-message") + 1]
        if mode == "sleep": time.sleep(2)
        if mode == "invalid": result = "not json"
        else: result = json.dumps({"should_suggest": True, "confidence": 0.9, "category": "missing_decision", "suggestion": "Define the retry owner.", "reason": "Ownership is unresolved.", "follow_up_question": None, "evidence_segment_ids": [], "state_patch": {"current_topic": "Retries", "add_decisions": [], "add_open_questions": ["Who owns retries?"], "add_risks": [], "add_action_items": [], "add_parking_lot": []}})
        open(output, "w").write(result)
    """))
    mock.chmod(mock.stat().st_mode | stat.S_IXUSR)
    settings = get_settings(); settings.codex_bin = str(mock); settings.codex_timeout_seconds = 5
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.get("/api/health")).status_code == 200
            providers = await client.get("/api/providers"); assert providers.status_code == 200, providers.text
            created = await client.post("/api/meetings", json={"title": "Integration", "goal": "Verify flow", "privacy_acknowledged": True}); assert created.status_code == 201, created.text
            meeting_id = created.json()["id"]
            for command, expected in (("start", "active"), ("pause", "paused"), ("resume", "active")):
                response = await client.post(f"/api/meetings/{meeting_id}/{command}"); assert response.status_code == 200, response.text; assert response.json()["meeting"]["status"] == expected
            run = await client.post(f"/api/meetings/{meeting_id}/ask", json={"question": "What is missing?"}); assert run.status_code == 200, run.text
            async def wait_status(run_id: str, terminal: set[str]) -> dict:
                for _ in range(100):
                    current = (await client.get(f"/api/meetings/{meeting_id}")).json()
                    found = next(item for item in current["codex_runs"] if item["id"] == run_id)
                    if found["status"] in terminal: return current
                    await asyncio.sleep(0.03)
                raise AssertionError("Codex run did not finish")
            completed = await wait_status(run.json()["run_id"], {"completed", "failed"}); assert completed["codex_runs"][0]["status"] == "completed"; assert completed["suggestions"]
            suggestion_id = completed["suggestions"][0]["id"]; accepted = await client.post(f"/api/suggestions/{suggestion_id}/accept"); assert accepted.json()["status"] == "accepted"
            os.environ["MOCK_CODEX_MODE"] = "invalid"; invalid = await client.post(f"/api/meetings/{meeting_id}/analyze"); invalid_detail = await wait_status(invalid.json()["run_id"], {"failed"}); assert any(item["status"] == "failed" for item in invalid_detail["codex_runs"])
            os.environ["MOCK_CODEX_MODE"] = "sleep"; settings.codex_timeout_seconds = 0.1; timed = await client.post(f"/api/meetings/{meeting_id}/analyze"); timed_detail = await wait_status(timed.json()["run_id"], {"timed_out"}); assert any(item["status"] == "timed_out" for item in timed_detail["codex_runs"])
            settings.codex_timeout_seconds = 5; cancel = await client.post(f"/api/meetings/{meeting_id}/analyze"); cancelled = await client.post(f"/api/codex-runs/{cancel.json()['run_id']}/cancel"); assert cancelled.json()["cancelled"] is True
            os.environ.pop("MOCK_CODEX_MODE", None)
            response = await client.post(f"/api/meetings/{meeting_id}/end"); assert response.json()["meeting"]["status"] == "ended"
            for export in ("markdown", "json", "vtt"):
                response = await client.post(f"/api/meetings/{meeting_id}/export/{export}"); assert response.status_code == 200
            detail = await client.get(f"/api/meetings/{meeting_id}"); assert detail.status_code == 200, detail.text
            migration = await client.post("/api/diagnostics/migrations"); assert migration.json()["valid"] is True
    print("integration check passed: lifecycle, Codex success/invalid/timeout/cancel, suggestions, exports, migrations")


if __name__ == "__main__": asyncio.run(main())
