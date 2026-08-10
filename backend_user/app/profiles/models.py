from datetime import date, datetime, time
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ProfileOnboardingData(BaseModel):
    target_role: str
    skills: list[str] = Field(min_length=1, max_length=20)
    experience_summary: str
    target_date: date
    target_company: str | None
    preferred_environment: str
    daily_notification_time: time
    assistant_style: Literal["friendly", "direct"]


class ProfileAssessment(BaseModel):
    score: int = Field(ge=0, le=100)
    level: Literal["beginner", "intermediate", "advanced"]
    summary: dict[str, Any]
    version: str
    model_name: str
    provider: str
    prompt_version: str
    rubric_version: str
    schema_version: str = "profile-assessment-v1"


class AssessmentSource(BaseModel):
    provider: str
    model: str
    prompt_version: str
    rubric_version: str


class ProfileRecord(ProfileOnboardingData):
    user_id: UUID
    assessment_score: int | None = Field(default=None, ge=0, le=100)
    assessment_level: Literal["beginner", "intermediate", "advanced"] | None = None
    assessment_summary: dict[str, Any] | None = None
    assessment_version: str | None = None
    assessed_at: datetime | None = None
    onboarding_completed_at: datetime | None = None
    assessment_result_id: UUID | None = None
    assessment_source: AssessmentSource | None = None
    draft_revision: int | None = Field(default=None, ge=0)
    snapshot_hash: str | None = Field(default=None, min_length=64, max_length=64)


class Score30(BaseModel):
    score: int = Field(ge=0, le=30)
    reason: str = Field(min_length=1, max_length=2000)


class Score20(BaseModel):
    score: int = Field(ge=0, le=20)
    reason: str = Field(min_length=1, max_length=2000)


class GeminiAssessmentDecision(BaseModel):
    skill_readiness: Score30
    experience_depth: Score30
    goal_clarity: Score20
    execution_readiness: Score20
