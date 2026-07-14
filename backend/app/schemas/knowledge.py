from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DecisionStatus = Literal["draft", "proposed", "confirmed", "rejected", "superseded", "archived"]
ActionStatus = Literal["open", "in_progress", "blocked", "completed", "archived"]


class DecisionWrite(BaseModel):
    meeting_id: str
    project_id: str | None = None
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=20000)
    owner: str | None = Field(default=None, max_length=100)
    status: DecisionStatus = "draft"
    confidence: float = Field(default=1, ge=0, le=1)
    evidence_segment_ids: list[str] = Field(default_factory=list, max_length=200)


class DecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str | None
    meeting_id: str
    title: str
    description: str
    owner: str | None
    status: str
    confidence: float
    version: int
    supersedes_id: str | None
    superseded_by_id: str | None
    evidence_segment_ids_json: list[str]
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime


class DecisionSupersede(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=20000)
    owner: str | None = Field(default=None, max_length=100)
    status: Literal["draft", "proposed", "confirmed"] = "draft"
    confidence: float = Field(default=1, ge=0, le=1)
    evidence_segment_ids: list[str] = Field(default_factory=list, max_length=200)


class ActionWrite(BaseModel):
    meeting_id: str
    project_id: str | None = None
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=20000)
    owner: str | None = Field(default=None, max_length=100)
    due_at: datetime | None = None
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    status: ActionStatus = "open"
    linked_decision_id: str | None = None
    evidence_segment_ids: list[str] = Field(default_factory=list, max_length=200)

class ActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str | None
    meeting_id: str
    title: str
    description: str
    owner: str | None
    due_at: datetime | None
    priority: str
    status: str
    linked_decision_id: str | None
    source_suggestion_id: str | None
    evidence_segment_ids_json: list[str]
    created_at: datetime
    updated_at: datetime


class KnowledgeDocumentWrite(BaseModel):
    project_id: str | None = None
    source_type: Literal["uploaded", "repository", "report", "note"] = "uploaded"
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=1_000_000)
    language: str = Field(default="und", min_length=2, max_length=20)
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str | None
    source_type: str
    title: str
    content: str
    language: str
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class KnowledgeSearchResult(BaseModel):
    id: str
    source_type: str
    project_id: str | None
    meeting_id: str | None = None
    title: str
    excerpt: str
    language: str = "und"
    status: str | None = None
    created_at: datetime
