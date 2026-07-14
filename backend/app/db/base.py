from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class AppSetting(Base, TimestampMixin):
    __tablename__ = "app_settings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    value_json: Mapped[Any] = mapped_column(JSON, default=dict)
    is_secret_reference: Mapped[bool] = mapped_column(Boolean, default=False)


class AuthCredential(Base, TimestampMixin):
    __tablename__ = "auth_credentials"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(500))
    role: Mapped[str] = mapped_column(String(40), default="admin")


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    credential_id: Mapped[str] = mapped_column(
        ForeignKey("auth_credentials.id", ondelete="CASCADE"), index=True
    )
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(100), index=True)
    resource_type: Mapped[str] = mapped_column(String(80), index=True)
    resource_id: Mapped[str | None] = mapped_column(String(100))
    details_json: Mapped[Any] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("scope", "key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    scope: Mapped[str] = mapped_column(String(200))
    key: Mapped[str] = mapped_column(String(200))
    request_hash: Mapped[str] = mapped_column(String(64))
    resource_type: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ModelProvider(Base, TimestampMixin):
    __tablename__ = "model_providers"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), index=True)
    provider_type: Mapped[str] = mapped_column(String(40))
    base_url: Mapped[str | None] = mapped_column(String(500))
    secret_ref: Mapped[str | None] = mapped_column(String(200))
    model: Mapped[str | None] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=60)
    max_retries: Mapped[int] = mapped_column(Integer, default=2)
    extra_json: Mapped[Any] = mapped_column(JSON, default=dict)
    health_status: Mapped[str] = mapped_column(String(20), default="unknown")
    last_latency_ms: Mapped[int | None] = mapped_column(Integer)


class Project(Base, TimestampMixin):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    goals: Mapped[str] = mapped_column(Text, default="")
    non_goals: Mapped[str] = mapped_column(Text, default="")
    default_language: Mapped[str] = mapped_column(String(20), default="zh-TW")


class ProjectGlossary(Base, TimestampMixin):
    __tablename__ = "project_glossary"
    __table_args__ = (UniqueConstraint("project_id", "term", "language"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    term: Mapped[str] = mapped_column(String(200))
    language: Mapped[str] = mapped_column(String(20), default="zh-TW")
    preferred_spelling: Mapped[str] = mapped_column(String(200), default="")
    translation: Mapped[str] = mapped_column(String(500), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    aliases_json: Mapped[Any] = mapped_column(JSON, default=list)
    do_not_translate: Mapped[bool] = mapped_column(Boolean, default=False)


class ProjectMemory(Base, TimestampMixin):
    __tablename__ = "project_memory"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(50), index=True)
    title: Mapped[str] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text)
    source_meeting_id: Mapped[str | None] = mapped_column(
        ForeignKey("meetings.id", ondelete="SET NULL")
    )
    source_decision_id: Mapped[str | None] = mapped_column(
        ForeignKey("decisions.id", ondelete="SET NULL")
    )
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class Meeting(Base, TimestampMixin):
    __tablename__ = "meetings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(200), index=True)
    goal: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(String(20), default="zh")
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    configuration_json: Mapped[Any] = mapped_column(JSON, default=dict)
    audio_saved: Mapped[bool] = mapped_column(Boolean, default=False)
    repository_context_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    repository_path: Mapped[str | None] = mapped_column(String(1000))
    participants: Mapped[list["Participant"]] = relationship(cascade="all, delete-orphan")
    transcripts: Mapped[list["TranscriptSegment"]] = relationship(cascade="all, delete-orphan")


class Participant(Base):
    __tablename__ = "participants"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    meeting_id: Mapped[str] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), index=True
    )
    display_name: Mapped[str] = mapped_column(String(100))
    speaker_label: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TranscriptSegment(Base, TimestampMixin):
    __tablename__ = "transcript_segments"
    __table_args__ = (UniqueConstraint("meeting_id", "sequence"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    meeting_id: Mapped[str] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    speaker_id: Mapped[str | None] = mapped_column(String(36))
    language: Mapped[str] = mapped_column(String(20), default="und")
    translated_language: Mapped[str | None] = mapped_column(String(20))
    start_ms: Mapped[int] = mapped_column(Integer)
    end_ms: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    translated_text: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    is_final: Mapped[bool] = mapped_column(Boolean, default=True)
    is_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)


class MeetingState(Base):
    __tablename__ = "meeting_states"
    __table_args__ = (UniqueConstraint("meeting_id", "version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    meeting_id: Mapped[str] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    current_topic: Mapped[str] = mapped_column(Text, default="")
    state_json: Mapped[Any] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CodexRun(Base):
    __tablename__ = "codex_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    meeting_id: Mapped[str] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), index=True
    )
    job_type: Mapped[str] = mapped_column(String(40))
    trigger: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30), index=True)
    profile: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(100))
    provider: Mapped[str | None] = mapped_column(String(100))
    request_json: Mapped[Any] = mapped_column(JSON, default=dict)
    response_json: Mapped[Any] = mapped_column(JSON, default=dict)
    sanitized_stderr: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Suggestion(Base, TimestampMixin):
    __tablename__ = "suggestions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    meeting_id: Mapped[str] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), index=True
    )
    codex_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("codex_runs.id", ondelete="SET NULL")
    )
    category: Mapped[str] = mapped_column(String(40))
    content: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text, default="")
    follow_up_question: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    trigger: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    evidence_segment_ids_json: Mapped[Any] = mapped_column(JSON, default=list)


class StateItemMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    meeting_id: Mapped[str] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), index=True
    )
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(40), default="user")
    source_suggestion_id: Mapped[str | None] = mapped_column(
        ForeignKey("suggestions.id", ondelete="SET NULL")
    )
    evidence_segment_ids_json: Mapped[Any] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Decision(Base, StateItemMixin):
    __tablename__ = "decisions"
    title: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    supersedes_id: Mapped[str | None] = mapped_column(
        ForeignKey("decisions.id", ondelete="SET NULL")
    )
    superseded_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("decisions.id", ondelete="SET NULL")
    )
    created_by: Mapped[str] = mapped_column(String(100), default="user")
    updated_by: Mapped[str] = mapped_column(String(100), default="user")


class OpenQuestion(Base, StateItemMixin):
    __tablename__ = "open_questions"
    status: Mapped[str] = mapped_column(String(20), default="open")
    owner: Mapped[str | None] = mapped_column(String(100))


class Risk(Base, StateItemMixin):
    __tablename__ = "risks"
    status: Mapped[str] = mapped_column(String(20), default="open")
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    probability: Mapped[float] = mapped_column(Float, default=0.5)
    owner: Mapped[str | None] = mapped_column(String(100))


class ActionItem(Base, StateItemMixin):
    __tablename__ = "action_items"
    title: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str | None] = mapped_column(String(100))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    priority: Mapped[str] = mapped_column(String(20), default="normal", index=True)
    status: Mapped[str] = mapped_column(String(20), default="open")
    linked_decision_id: Mapped[str | None] = mapped_column(
        ForeignKey("decisions.id", ondelete="SET NULL")
    )


class KnowledgeDocument(Base, TimestampMixin):
    __tablename__ = "knowledge_documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(40), default="uploaded", index=True)
    title: Mapped[str] = mapped_column(String(300), index=True)
    content: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(20), default="und", index=True)
    metadata_json: Mapped[Any] = mapped_column(JSON, default=dict)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("meeting_id", "sequence"),
        Index("ix_events_type_created", "type", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    meeting_id: Mapped[str] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(60))
    source: Mapped[str] = mapped_column(String(40))
    payload_json: Mapped[Any] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AudioChunk(Base):
    __tablename__ = "audio_chunks"
    __table_args__ = (UniqueConstraint("meeting_id", "sequence"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    meeting_id: Mapped[str] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    path: Mapped[str | None] = mapped_column(String(1000))
    start_ms: Mapped[int] = mapped_column(Integer)
    end_ms: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
