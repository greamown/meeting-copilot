import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.db.base import Meeting, ProjectGlossary, ProjectMemory, TranscriptSegment
from app.schemas.common import ProviderBase
from app.schemas.meeting import EngineOutput, SuggestionSignals
from app.services.engine import build_request
from app.services.glossary import normalize_transcript, normalize_translation
from app.services.stt import whisper_language
from app.services.trigger import (
    TriggerContext,
    accumulate_new_characters,
    decide_trigger,
    merge_overlap,
    similar,
)


def test_trigger_suppressors_and_manual_override():
    context = TriggerContext(
        text="brief update", status="active", automatic_enabled=True, new_characters=20
    )
    assert decide_trigger(context).suppressed_by == "insufficient_transcript"
    assert decide_trigger(context, manual=True).trigger == "manual_ask"


def test_trigger_question_and_cooldown():
    context = TriggerContext(
        text="我們要選哪個方案？" * 30, status="active", automatic_enabled=True, new_characters=500
    )
    assert decide_trigger(context).trigger == "explicit_question"
    cooling = TriggerContext(**{**context.__dict__, "last_codex_at": datetime.now(UTC)})
    assert decide_trigger(cooling).suppressed_by == "codex_cooldown"


def test_short_explicit_question_bypasses_periodic_character_threshold():
    decision = decide_trigger(TriggerContext("現在要選哪個方案？", "active", True, 10))
    assert decision.invoke
    assert decision.trigger == "explicit_question"


def test_suggestion_signal_score_requires_multiple_strong_signals():
    low = SuggestionSignals(question_detected=True, decision_point_detected=True)
    high = SuggestionSignals(
        question_detected=True,
        discussion_stuck=True,
        missing_risk_detected=True,
        contradiction_detected=True,
        decision_point_detected=True,
    )
    assert low.score() == 0.45
    assert high.score() == 1


def test_overlap_and_similarity():
    assert merge_overlap("hello world", "world again") == "again"
    assert similar("Define a task lease", "define a task lease")
    assert not similar("database index", "speech playback")


def test_transcript_characters_accumulate_across_stt_windows():
    accumulated = accumulate_new_characters({"new_transcript_characters": 180}, 140)
    assert accumulated == 320
    assert not decide_trigger(
        TriggerContext("討論內容", "active", True, accumulated)
    ).suppressed_by


def test_codex_schema_rejects_unknown_state_operation():
    payload = {
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
            "delete_decisions": ["x"],
        },
    }
    with pytest.raises(ValidationError):
        EngineOutput.model_validate(payload)


def test_engine_response_schema_is_strict_output_compatible():
    schema = json.loads(Path("schemas/engine-response.schema.json").read_text())

    def check(node: object) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and node.get("additionalProperties") is False:
                assert set(node.get("required", [])) == set(node.get("properties", {}))
            for value in node.values():
                check(value)
        elif isinstance(node, list):
            for value in node:
                check(value)

    check(schema)


def test_provider_configuration_validation():
    assert ProviderBase(
        id="claude-local", name="Claude Code", role="reasoning", provider_type="claude_code"
    ).provider_type == "claude_code"
    with pytest.raises(ValidationError):
        ProviderBase(id="x", name="bad", role="chat", provider_type="codex_cli")


def test_provider_configuration_rejects_nested_inline_secrets():
    with pytest.raises(ValidationError, match="use secret_ref"):
        ProviderBase(
            id="unsafe-provider",
            name="unsafe",
            role="tts",
            provider_type="custom_http",
            extra={"headers": {"api-key": "must-not-be-stored"}},
        )


def test_defaults_are_local_first():
    settings = Settings()
    assert settings.stt_device == "cuda"
    assert settings.stt_model == "large-v3-turbo"
    assert settings.host == "127.0.0.1"


def test_whisper_language_normalization():
    assert whisper_language("auto") is None
    assert whisper_language("zh-TW") == "zh"
    assert whisper_language("zh-CN") == "zh"
    assert whisper_language("en-US") == "en"


def test_glossary_normalizes_transcript_and_translation():
    glossary = ProjectGlossary(
        project_id="project-1",
        term="Codex",
        language="en",
        preferred_spelling="Codex CLI",
        translation="程式助理",
        aliases_json=["codecks"],
        do_not_translate=True,
    )
    assert normalize_transcript("use codecks now", [glossary]) == "use Codex CLI now"
    assert normalize_translation("使用程式助理", [glossary]) == "使用Codex CLI"


def test_codex_context_is_bounded_and_contains_project_memory():
    meeting = Meeting(
        id="meeting-1",
        project_id="project-1",
        title="Architecture",
        goal="Choose an API",
        language="zh-TW",
        configuration_json={
            "secondary_language": "ja",
            "suggestion_language": "en",
            "summary_language": "zh-TW",
            "translation_language": "zh-TW",
            "analysis_language_mode": "both",
            "review_roles": ["security"],
        },
    )
    transcripts = [
        TranscriptSegment(
            id=f"segment-{index}",
            meeting_id=meeting.id,
            sequence=index,
            start_ms=index * 1000,
            end_ms=(index + 1) * 1000,
            text="x" * 5000,
            language="zh",
        )
        for index in range(4)
    ]
    memory = ProjectMemory(
        id="memory-1",
        project_id="project-1",
        category="security_constraints",
        title="Local only",
        content="Do not send audio to cloud services.",
        confidence=1,
        version=2,
    )
    glossary = ProjectGlossary(
        project_id="project-1",
        term="Codex",
        language="en",
        preferred_spelling="Codex CLI",
        aliases_json=["codex"],
        do_not_translate=True,
    )
    request = build_request(
        meeting, transcripts, [], "manual_ask", "What next?", [memory], [glossary]
    )
    assert request["project_id"] == "project-1"
    assert request["project_memory"][0]["title"] == "Local only"
    assert request["glossary"][0]["do_not_translate"] is True
    assert request["language"] == {
        "input": "zh-TW",
        "secondary": "ja",
        "output": "en",
        "summary": "zh-TW",
        "translation": "zh-TW",
        "analysis_mode": "both",
    }
    assert request["review_roles"] == ["security"]
    assert sum(len(row["text"]) for row in request["recent_transcript"]) <= 12_000


def test_build_cli_command_selects_engine(tmp_path):
    from app.services.engine import build_cli_command, engine_of, extract_claude_result

    assert engine_of("claude_code") == "claude"
    assert engine_of("codex_cli") == "codex" and engine_of(None) == "codex"

    schema = tmp_path / "schema.json"
    schema.write_text('{"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"}')
    settings = Settings()
    out = tmp_path / "out.json"

    codex_cmd = build_cli_command("codex", "gpt-x", "p1", settings, tmp_path, schema, out)
    assert codex_cmd[0] == settings.codex_bin and "--output-schema" in codex_cmd
    assert str(schema) in codex_cmd  # codex takes the schema path

    claude_cmd = build_cli_command("claude", None, None, settings, tmp_path, schema, out)
    assert claude_cmd[0] == settings.claude_bin and "--json-schema" in claude_cmd
    inline = claude_cmd[claude_cmd.index("--json-schema") + 1]
    assert "$schema" not in inline  # meta-ref stripped; claude rejects it

    envelope = '{"is_error": false, "subtype": "success", "result": "{\\"ok\\": true}"}'
    assert extract_claude_result(envelope) == '{"ok": true}'
    with pytest.raises(RuntimeError):
        extract_claude_result('{"is_error": true, "result": "boom"}')
