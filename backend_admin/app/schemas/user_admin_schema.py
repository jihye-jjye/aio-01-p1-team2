"""관리자 사용자 목록·상세·수정 API Schema."""

from datetime import date, datetime, time
from enum import StrEnum
from uuid import UUID

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"


class AdminUserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    target_role: str | None = None
    skills: list[str] = Field(default_factory=list)
    experience_summary: str | None = None
    target_date: date | None = None
    target_company: str | None = None
    preferred_environment: str | None = None
    assistant_style: str
    daily_notification_time: time | None = None
    assessment_score: int | None = None
    assessment_level: str | None = None
    assessment_summary: dict[str, Any] | None = None
    assessed_at: datetime | None = None
    assessment_version: str | None = None
    assessment_result_id: UUID | None = None
    onboarding_completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AdminUserListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    login_id: str
    role: UserRole
    user_exp: int
    is_active: bool
    last_login_at: datetime | None
    failed_login_count: int
    locked_until: datetime | None
    created_at: datetime
    updated_at: datetime
    profile: AdminUserProfile | None = None


class AdminUserDetail(AdminUserListItem):
    pass


class AdminUserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: bool


class AdminUserListResponse(BaseModel):
    items: list[AdminUserListItem]
    page: int = Field(ge=1)
    size: int = Field(ge=1)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class AdminUserQueryParams(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    search: str | None = Field(default=None, min_length=1, max_length=50)
    role: UserRole | None = None
    is_active: bool | None = None
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)
