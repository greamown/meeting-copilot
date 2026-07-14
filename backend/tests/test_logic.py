from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.common import ProviderBase
from app.schemas.meeting import CodexOutput
from app.services.trigger import TriggerContext, decide_trigger, merge_overlap, similar


def test_trigger_suppressors_and_manual_override():
    context = TriggerContext(text="Should we decide?", status="active", automatic_enabled=True, new_characters=20)
    assert decide_trigger(context).suppressed_by == "insufficient_transcript"
    assert decide_trigger(context, manual=True).trigger == "manual_ask"


def test_trigger_question_and_cooldown():
    context = TriggerContext(text="我們要選哪個方案？" * 30, status="active", automatic_enabled=True, new_characters=500)
    assert decide_trigger(context).trigger == "explicit_question"
    cooling = TriggerContext(**{**context.__dict__, "last_codex_at": datetime.now(timezone.utc)})
    assert decide_trigger(cooling).suppressed_by == "codex_cooldown"


def test_overlap_and_similarity():
    assert merge_overlap("hello world", "world again") == "again"
    assert similar("Define a task lease", "define a task lease")
    assert not similar("database index", "speech playback")


def test_codex_schema_rejects_unknown_state_operation():
    payload = {"should_suggest": False, "confidence": 0, "category": "no_material_value", "suggestion": "", "reason": "none", "follow_up_question": None, "evidence_segment_ids": [], "state_patch": {"current_topic": None, "add_decisions": [], "add_open_questions": [], "add_risks": [], "add_action_items": [], "add_parking_lot": [], "delete_decisions": ["x"]}}
    with pytest.raises(ValidationError): CodexOutput.model_validate(payload)


def test_provider_configuration_validation():
    with pytest.raises(ValidationError): ProviderBase(id="x", name="bad", role="chat", provider_type="codex_cli")


def test_defaults_are_local_first():
    settings = Settings()
    assert settings.stt_device == "cuda"
    assert settings.stt_model == "large-v3-turbo"
    assert settings.host == "127.0.0.1"
