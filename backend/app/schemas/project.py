from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LanguageCode = Literal["zh-TW", "zh-CN", "en", "ja", "ko"]
MemoryCategory = Literal[
    "architecture",
    "apis",
    "data_model",
    "infrastructure",
    "security_constraints",
    "performance_constraints",
    "business_constraints",
    "naming_conventions",
    "coding_conventions",
    "deployment_conventions",
    "known_risks",
    "lessons_learned",
    "rejected_alternatives",
    "glossary",
    "stakeholders",
    "project_goals",
    "project_non_goals",
]


class ProjectBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10000)
    goals: str = Field(default="", max_length=20000)
    non_goals: str = Field(default="", max_length=20000)
    default_language: LanguageCode = "zh-TW"


class ProjectRead(ProjectBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    updated_at: datetime


class ProjectDetail(ProjectRead):
    meeting_count: int
    memory_count: int
    glossary_count: int


class GlossaryBase(BaseModel):
    term: str = Field(min_length=1, max_length=200)
    language: LanguageCode = "zh-TW"
    preferred_spelling: str = Field(default="", max_length=200)
    translation: str = Field(default="", max_length=500)
    description: str = Field(default="", max_length=5000)
    aliases: list[str] = Field(default_factory=list, max_length=50)
    do_not_translate: bool = False


class GlossaryRead(GlossaryBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    created_at: datetime
    updated_at: datetime


class ProjectMemoryBase(BaseModel):
    category: MemoryCategory
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=50000)
    source_meeting_id: str | None = None
    source_decision_id: str | None = None
    confidence: float = Field(default=1, ge=0, le=1)
    status: Literal["active", "archived", "superseded"] = "active"


class ProjectMemoryRead(ProjectMemoryBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    version: int
    created_at: datetime
    updated_at: datetime
