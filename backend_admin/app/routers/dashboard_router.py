"""관리자 대시보드 조회 API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import get_current_admin
from app.schemas.dashboard_schema import AdminDashboardResponse
from app.services.dashboard_service import DashboardService
from app.services.exceptions import DashboardStorageError


dashboard_router = APIRouter(
    prefix="/api/v1/admin/dashboard",
    tags=["Admin Dashboard"],
    dependencies=[Depends(get_current_admin)],
)
dashboard_service = DashboardService()


@dashboard_router.get(
    "",
    response_model=AdminDashboardResponse,
    summary="관리자 대시보드 조회",
    description=(
        "일반 사용자 계정, 온보딩, 역량 평가, 로드맵, 퀘스트, "
        "일별 신규 가입자와 최근 가입 사용자 정보를 한 번에 반환합니다. "
        "모든 날짜 기준은 Asia/Seoul이며 관리자 역할 계정은 집계에서 제외됩니다."
    ),
    response_description=(
        "집계 시각·기간, 사용자·온보딩·평가·로드맵·퀘스트 지표, "
        "일별 가입 추이와 최근 사용자 5명"
    ),
    responses={
        503: {"description": "대시보드 DB 함수 호출 또는 응답 검증 실패"},
    },
)
def get_dashboard(
    days: Annotated[
        int,
        Query(
            ge=1,
            le=90,
            description="오늘을 포함한 조회 일수",
        ),
    ] = 7,
) -> AdminDashboardResponse:
    try:
        return dashboard_service.get_dashboard(days)
    except DashboardStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
