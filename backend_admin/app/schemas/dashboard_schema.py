"""관리자 대시보드 집계 API Schema."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DashboardPeriod(BaseModel):
    days: int = Field(ge=1, le=90, description="오늘을 포함한 조회 일수")
    start_at: datetime = Field(description="조회 기간 시작 시각")
    end_at: datetime = Field(description="집계 생성 시점")


class DashboardUserMetrics(BaseModel):
    total_users: int = Field(ge=0, description="관리자를 제외한 전체 사용자 수")
    active_accounts: int = Field(ge=0, description="활성 사용자 계정 수")
    inactive_accounts: int = Field(ge=0, description="비활성 사용자 계정 수")
    new_users: int = Field(ge=0, description="조회 기간 내 신규 가입자 수")


class DashboardOnboardingMetrics(BaseModel):
    profile_count: int = Field(ge=0, description="프로필이 생성된 사용자 수")
    completed_count: int = Field(ge=0, description="온보딩 완료 사용자 수")
    incomplete_count: int = Field(ge=0, description="온보딩 미완료 사용자 수")
    completion_rate: float = Field(
        ge=0,
        le=100,
        description="전체 사용자 대비 온보딩 완료율",
    )


class DashboardAssessmentLevelDistribution(BaseModel):
    beginner: int = Field(ge=0)
    intermediate: int = Field(ge=0)
    advanced: int = Field(ge=0)


class DashboardAssessmentMetrics(BaseModel):
    assessed_users: int = Field(ge=0, description="역량 평가 완료 사용자 수")
    average_score: float = Field(ge=0, le=100, description="평균 역량 평가 점수")
    level_distribution: DashboardAssessmentLevelDistribution


class DashboardPlanStatusDistribution(BaseModel):
    draft: int = Field(ge=0)
    active: int = Field(ge=0)
    completed: int = Field(ge=0)
    expired: int = Field(ge=0)
    superseded: int = Field(ge=0)
    rejected: int = Field(ge=0)


class DashboardRoadmapMetrics(BaseModel):
    users_with_plans: int = Field(ge=0, description="로드맵을 한 번이라도 생성한 사용자 수")
    active_plans: int = Field(ge=0, description="현재 활성 로드맵 수")
    completed_plans: int = Field(ge=0, description="완료된 로드맵 수")
    expired_plans: int = Field(ge=0, description="만료된 로드맵 수")
    status_distribution: DashboardPlanStatusDistribution


class DashboardQuestMetrics(BaseModel):
    total: int = Field(ge=0, description="진행률에 반영되는 전체 퀘스트 수")
    completed: int = Field(ge=0, description="완료 퀘스트 수")
    in_progress: int = Field(ge=0, description="진행 중 퀘스트 수")
    pending: int = Field(ge=0, description="대기 퀘스트 수")
    completion_rate: float = Field(ge=0, le=100, description="전체 퀘스트 완료율")
    scheduled_today: int = Field(ge=0, description="오늘 예정된 전체 일정 수")
    completed_today: int = Field(ge=0, description="오늘 완료된 전체 일정 수")
    overdue: int = Field(ge=0, description="예정 시각이 지났지만 완료되지 않은 일정 수")
    interviews_today: int = Field(ge=0, description="오늘 예정된 면접 일정 수")


class DashboardDailySignup(BaseModel):
    date: date
    count: int = Field(ge=0)


class DashboardRecentUser(BaseModel):
    id: UUID
    login_id: str
    is_active: bool
    user_exp: int = Field(ge=0, le=100)
    target_role: str | None = None
    onboarding_completed: bool
    created_at: datetime


class AdminDashboardResponse(BaseModel):
    generated_at: datetime = Field(description="대시보드 집계 생성 시각")
    period: DashboardPeriod
    users: DashboardUserMetrics
    onboarding: DashboardOnboardingMetrics
    assessment: DashboardAssessmentMetrics
    roadmaps: DashboardRoadmapMetrics
    quests: DashboardQuestMetrics
    daily_signups: list[DashboardDailySignup]
    recent_users: list[DashboardRecentUser]
