from __future__ import annotations

from datetime import date, time
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.profiles.models import ProfileAssessment, ProfileRecord

type ProfileField = Literal[
    "target_role",
    "skills",
    "experience_summary",
    "target_date",
    "target_company",
    "preferred_environment",
    "daily_notification_time",
    "assistant_style",
]

PROFILE_FIELDS: tuple[ProfileField, ...] = (
    "target_role",
    "skills",
    "experience_summary",
    "target_date",
    "target_company",
    "preferred_environment",
    "daily_notification_time",
    "assistant_style",
)


class ConversationMessage(BaseModel):
    turn_id: UUID
    role: Literal["user", "assistant"]
    text: str = Field(min_length=1, max_length=4000)


class FieldEvidence(BaseModel):
    turn_id: UUID
    quote: str = Field(min_length=1, max_length=1000)


class _FieldUpdate(BaseModel):
    evidence: list[FieldEvidence] = Field(min_length=1)


class TargetRoleUpdate(_FieldUpdate):
    field: Literal["target_role"]
    value: str = Field(min_length=1, max_length=200)


class SkillsUpdate(_FieldUpdate):
    field: Literal["skills"]
    value: list[str] = Field(min_length=1, max_length=20)


class ExperienceSummaryUpdate(_FieldUpdate):
    field: Literal["experience_summary"]
    value: str = Field(min_length=1, max_length=4000)


class TargetDateUpdate(_FieldUpdate):
    field: Literal["target_date"]
    value: date


class TargetCompanyUpdate(_FieldUpdate):
    field: Literal["target_company"]
    value: str | None = Field(max_length=200)


class PreferredEnvironmentUpdate(_FieldUpdate):
    field: Literal["preferred_environment"]
    value: str = Field(min_length=1, max_length=1000)


class NotificationTimeUpdate(_FieldUpdate):
    field: Literal["daily_notification_time"]
    value: time


class AssistantStyleUpdate(_FieldUpdate):
    field: Literal["assistant_style"]
    value: Literal["friendly", "direct"]


GeminiFieldUpdate = Annotated[
    TargetRoleUpdate
    | SkillsUpdate
    | ExperienceSummaryUpdate
    | TargetDateUpdate
    | TargetCompanyUpdate
    | PreferredEnvironmentUpdate
    | NotificationTimeUpdate
    | AssistantStyleUpdate,
    Field(discriminator="field"),
]


class GeminiConversationDecision(BaseModel):
    assistant_message: str = Field(min_length=1, max_length=4000)
    field_updates: list[GeminiFieldUpdate] = Field(default_factory=list, max_length=8)
    next_focus: ProfileField | None = None


class EngineInfo(BaseModel):
    provider: Literal["google"] = "google"
    model: Literal["gemini-3.6-flash"] = "gemini-3.6-flash"
    api_version: Literal["v1"] = "v1"
    mode: Literal["live"] = "live"
    conversation_prompt_version: Literal["onboarding-conversation-v1"] = (
        "onboarding-conversation-v1"
    )
    assessment_prompt_version: Literal["onboarding-assessment-v1", "onboarding-assessment-v2"] = (
        "onboarding-assessment-v2"
    )


class OnboardingPayload(BaseModel):
    draft_revision: int = Field(default=0, ge=0)
    draft_profile: dict[str, Any] = Field(default_factory=dict)
    answered_fields: list[ProfileField] = Field(default_factory=list)
    missing_fields: list[ProfileField] = Field(default_factory=lambda: list(PROFILE_FIELDS))
    assessment: ProfileAssessment | None = None
    engine: EngineInfo = Field(default_factory=EngineInfo)
    stored_profile: ProfileRecord | None = None
    existing_profile: dict[str, Any] | None = None


class OnboardingResponse(BaseModel):
    session_id: UUID
    flow: Literal["onboarding"] = "onboarding"
    step: Literal["conversation", "review", "completed"]
    assistant_message: str = Field(min_length=1, max_length=4000)
    choices: list[str] = Field(default_factory=list)
    payload: OnboardingPayload
    completed: bool = False


class ProcessedOnboardingRequest(BaseModel):
    fingerprint: str
    response: OnboardingResponse


class OnboardingState(BaseModel):
    user_id: UUID
    session_id: UUID
    phase: Literal["collecting", "review", "completed"] = "collecting"
    messages: list[ConversationMessage] = Field(default_factory=list)
    draft_profile: dict[str, Any] = Field(default_factory=dict)
    answered_fields: list[ProfileField] = Field(default_factory=list)
    missing_fields: list[ProfileField] = Field(default_factory=lambda: list(PROFILE_FIELDS))
    draft_revision: int = Field(default=0, ge=0)
    assessment: ProfileAssessment | None = None
    processed_requests: dict[str, ProcessedOnboardingRequest] = Field(default_factory=dict)
    existing_profile: dict[str, Any] | None = None
