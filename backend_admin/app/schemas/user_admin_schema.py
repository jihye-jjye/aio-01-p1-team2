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


class AdminPlanSummary(BaseModel):
    id: UUID
    source_saved_job_id: UUID | None = None
    proposal_result_id: UUID | None = None
    previous_plan_id: UUID | None = None

    title: str
    summary: str | None = None
    goal_snapshot: dict[str, Any]

    starts_on: date
    ends_on: date
    total_task_count: int
    final_progress: int | None = None

    status: str
    activated_at: datetime | None = None
    ended_at: datetime | None = None
    archived_at: datetime | None = None

    created_at: datetime
    updated_at: datetime


class AdminQuestItem(BaseModel):
    id: UUID
    plan_id: UUID | None = None
    saved_job_id: UUID | None = None

    kind: str
    title: str
    description: str | None = None

    scheduled_at: datetime | None = None
    remind_at: datetime | None = None

    status: str
    plan_day: int | None = None
    slot: int | None = None

    detail_status: str
    counts_toward_progress: bool
    metadata: dict[str, Any]

    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AdminQuestProgress(BaseModel):
    total: int = Field(ge=0)
    completed: int = Field(ge=0)
    in_progress: int = Field(ge=0)
    pending: int = Field(ge=0)
    progress_percent: int = Field(ge=0, le=100)
    is_final: bool = False


class AdminRoadmapHistoryItem(BaseModel):
    plan: AdminPlanSummary
    quests: list[AdminQuestItem]
    progress: AdminQuestProgress


class AdminRoadmapHistoryResponse(BaseModel):
    login_id: str = Field(description="조회 대상 사용자의 로그인 아이디")
    items: list[AdminRoadmapHistoryItem] = Field(
        description="최신 계획부터 정렬된 로드맵 이력"
    )


class AdminQuestOverviewResponse(BaseModel):
    login_id: str = Field(description="조회 대상 사용자의 로그인 아이디")
    quests: list[AdminQuestItem] = Field(
        description="로드맵 소속 및 독립 일정을 포함한 전체 퀘스트"
    )
    active_plan_progress: AdminQuestProgress = Field(
        description="현재 활성 계획의 진행률. 활성 계획이 없으면 모두 0"
    )


class AdminUserOverview(BaseModel):
    account: AdminUserDetail = Field(
        description="계정 상태, 로그인 정보, 취업 프로필과 역량 평가"
    )
    # 기존 관리자 화면과의 호환성을 위해 평면 목록도 유지한다.
    plans: list[AdminPlanSummary] = Field(
        description="사용자의 전체 계획 목록"
    )
    quests: list[AdminQuestItem] = Field(
        description="사용자의 전체 퀘스트 및 일정 목록"
    )
    quest_progress: AdminQuestProgress = Field(
        description="현재 활성 계획의 퀘스트 진행률"
    )
    roadmap_history: list[AdminRoadmapHistoryItem] = Field(
        description="계획별 퀘스트와 진행률을 묶은 로드맵 이력"
    )
    last_login_at: datetime | None = Field(
        description="사용자의 마지막 로그인 시각"
    )
