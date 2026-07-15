from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MeetingCreate(BaseModel):
    project_id: str | None = None
    title: str = Field(min_length=1, max_length=200)
    goal: str = Field(default="", max_length=5000)
    language: Literal["auto", "zh-TW", "zh-CN", "en", "ja", "ko"] = "auto"
    secondary_language: Literal["none", "zh-TW", "zh-CN", "en", "ja", "ko"] = "none"
    transcript_display_language: Literal["original", "zh-TW", "zh-CN", "en", "ja", "ko"] = (
        "original"
    )
    translation_language: Literal["none", "zh-TW", "zh-CN", "en", "ja", "ko"] = "none"
    analysis_language_mode: Literal["original", "translated", "both"] = "original"
    suggestion_language: Literal["zh-TW", "zh-CN", "en", "ja", "ko"] = "zh-TW"
    summary_language: Literal["zh-TW", "zh-CN", "en", "ja", "ko"] = "zh-TW"
    export_language: Literal["original", "zh-TW", "zh-CN", "en", "ja", "ko"] = "original"
    tts_language: Literal["zh-TW", "zh-CN", "en", "ja", "ko"] = "zh-TW"
    tts_voice: str = Field(default="", max_length=200)
    tts_rate: float = Field(default=1, ge=0.5, le=2)
    tts_volume: float = Field(default=1, ge=0, le=1)
    stt_provider_id: str | None = None
    tts_provider_id: str | None = None
    codex_profile: str | None = None
    analysis_engine: Literal["codex", "claude"] | None = None  # None → global default
    automatic_analysis_enabled: bool = True
    analysis_interval_seconds: int = Field(default=120, ge=30, le=3600)
    suggestion_cooldown_seconds: int = Field(default=180, ge=0, le=3600)
    human_approval_before_speech: bool = True
    save_audio: bool = False
    repository_context_enabled: bool = False
    repository_path: str | None = None
    repository_read_only: bool = True
    reference_notes: str = Field(default="", max_length=50000)
    participants: list[str] = Field(default_factory=list, max_length=100)
    privacy_acknowledged: bool

    @model_validator(mode="after")
    def validate_privacy(self) -> "MeetingCreate":
        if not self.privacy_acknowledged:
            raise ValueError("Privacy notice acknowledgement is required")
        if self.save_audio and not self.privacy_acknowledged:
            raise ValueError("Explicit consent is required before saving audio")
        if self.repository_context_enabled and not self.repository_path:
            raise ValueError("Repository path is required when repository context is enabled")
        return self


class MeetingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str | None
    title: str
    goal: str
    language: str
    status: str
    started_at: datetime | None
    ended_at: datetime | None
    configuration_json: dict[str, Any]
    audio_saved: bool
    repository_context_enabled: bool
    repository_path: str | None
    created_at: datetime
    updated_at: datetime


class TranscriptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    meeting_id: str
    sequence: int
    speaker_id: str | None
    language: str
    translated_language: str | None
    start_ms: int
    end_ms: int
    text: str
    translated_text: str | None
    confidence: float | None
    is_final: bool
    is_edited: bool
    is_pinned: bool
    created_at: datetime


class TranscriptEdit(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    speaker_id: str | None = None
    is_pinned: bool | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, ge=0)
    repository_context: bool = False


class StatePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_topic: str | None = Field(default=None, max_length=500)
    add_decisions: list[str] = Field(default_factory=list, max_length=20)
    add_open_questions: list[str] = Field(default_factory=list, max_length=20)
    add_risks: list[str] = Field(default_factory=list, max_length=20)
    add_action_items: list[str] = Field(default_factory=list, max_length=20)
    add_parking_lot: list[str] = Field(default_factory=list, max_length=20)
    add_project_memory: list[str] = Field(default_factory=list, max_length=20)


class SummaryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_topic: str | None = Field(default=None, max_length=500)
    discussion_summary: str | None = Field(default=None, max_length=5000)


class TranscriptTranslation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    segment_id: str
    language: Literal["zh-TW", "zh-CN", "en", "ja", "ko"]
    text: str = Field(min_length=1, max_length=20000)


SuggestionCategory = Literal[
    "answer",
    "missing_decision",
    "unresolved_question",
    "contradiction",
    "risk",
    "alternative",
    "summary",
    "action_item",
    "off_topic",
    "no_material_value",
]


class EngineOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    should_suggest: bool
    confidence: float = Field(ge=0, le=1)
    category: SuggestionCategory
    suggestion: str = Field(max_length=1200)
    reason: str = Field(max_length=2000)
    follow_up_question: str | None = Field(default=None, max_length=1000)
    evidence_segment_ids: list[str]
    summary_patch: SummaryPatch = Field(default_factory=SummaryPatch)
    state_patch: StatePatch
    next_steps: list[str] = Field(default_factory=list, max_length=20)
    suggested_agenda: list[str] = Field(default_factory=list, max_length=20)
    translations: list[TranscriptTranslation] = Field(default_factory=list, max_length=100)


class SuggestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    meeting_id: str
    codex_run_id: str | None
    category: str
    content: str
    reason: str
    follow_up_question: str | None
    confidence: float
    trigger: str
    status: str
    evidence_segment_ids_json: list[str]
    created_at: datetime
    updated_at: datetime


class SuggestionEdit(BaseModel):
    content: str = Field(min_length=1, max_length=1200)


class ManualSuggestionCreate(SuggestionEdit):
    category: Literal[
        "architecture",
        "security",
        "reliability",
        "performance",
        "cost",
        "process",
        "clarification",
        "contradiction",
        "action_item",
        "decision",
        "risk",
        "open_question",
        "other",
    ] = "other"
    reason: str = Field(default="Added by a meeting participant", max_length=2000)


class StateItemCreate(BaseModel):
    kind: Literal["decision", "open_question", "risk", "action_item", "parking_lot"]
    content: str = Field(min_length=1, max_length=2000)
    owner: str | None = Field(default=None, max_length=100)


class MeetingDetail(BaseModel):
    meeting: MeetingRead
    transcripts: list[TranscriptRead]
    suggestions: list[SuggestionRead]
    decisions: list[dict[str, Any]]
    open_questions: list[dict[str, Any]]
    risks: list[dict[str, Any]]
    action_items: list[dict[str, Any]]
    codex_runs: list[dict[str, Any]]


class CommandResponse(BaseModel):
    meeting: MeetingRead


class EngineRunResponse(BaseModel):
    run_id: str
    status: str
