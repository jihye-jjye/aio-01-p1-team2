"""관리자 사용자 목록·상세·상태 변경 API."""

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.core.dependencies import get_current_admin
from app.schemas.user_admin_schema import (
    AdminUserDetail,
    AdminUserListResponse,
    AdminUserOverview,
    AdminQuestOverviewResponse,
    AdminRoadmapHistoryResponse,
    AdminUserQueryParams,
    AdminUserUpdate,
)
from app.services.exceptions import (
    UserAdminStorageError,
    UserDeleteForbiddenError,
    UserNotFoundError,
)
from app.services.user_admin_service import UserAdminService

user_admin_router = APIRouter(
    prefix="/api/v1/admin/users",
    tags=["User Admin"],
    dependencies=[Depends(get_current_admin)],
)
user_admin_service = UserAdminService()
LoginIdPath = Annotated[
    str,
    Path(
        min_length=4,
        max_length=50,
        pattern=r"^[a-zA-Z0-9._-]+$",
        description="회원가입 시 사용한 로그인 아이디",
        examples=["roadmap_user"],
    ),
]


@user_admin_router.get(
    "/by-login-id/{login_id}/overview",
    response_model=AdminUserOverview,
    summary="로그인 아이디로 사용자 종합 정보 조회",
    description=(
        "`login_id`에 해당하는 사용자의 계정·프로필, 전체 계획, 전체 퀘스트, "
        "활성 계획 진행률, 계획별 로드맵 이력을 한 번에 반환합니다. 응답이 크므로 "
        "로드맵 화면은 `/by-login-id/{login_id}/roadmaps`, 퀘스트 화면은 "
        "`/by-login-id/{login_id}/quests` 사용을 권장합니다."
    ),
    response_description=(
        "account(계정·프로필), plans(전체 계획), quests(전체 퀘스트), "
        "quest_progress(활성 계획 진행률), roadmap_history(계획별 이력), "
        "last_login_at(최근 로그인 시각)"
    ),
)
def get_user_overview(login_id: LoginIdPath) -> AdminUserOverview:
    try:
        return user_admin_service.get_user_overview_by_login_id(login_id)
    except (UserNotFoundError, UserAdminStorageError) as exc:
        _raise_user_http_error(exc)


@user_admin_router.get(
    "/by-login-id/{login_id}/roadmaps",
    response_model=AdminRoadmapHistoryResponse,
    summary="로그인 아이디로 로드맵 이력 조회",
    description=(
        "사용자의 모든 계획을 최신순으로 반환합니다. 각 items 항목은 plan(계획), "
        "quests(그 계획에 속한 퀘스트), progress(그 계획의 진행률)로 구성됩니다."
    ),
    response_description=(
        "login_id와 계획별 plan·quests·progress가 결합된 roadmap items"
    ),
)
def get_user_roadmaps(
    login_id: LoginIdPath,
) -> AdminRoadmapHistoryResponse:
    try:
        return user_admin_service.get_user_roadmaps_by_login_id(login_id)
    except (UserNotFoundError, UserAdminStorageError) as exc:
        _raise_user_http_error(exc)


@user_admin_router.get(
    "/by-login-id/{login_id}/quests",
    response_model=AdminQuestOverviewResponse,
    summary="로그인 아이디로 퀘스트와 진행률 조회",
    description=(
        "사용자의 전체 퀘스트·일정과 현재 활성 계획의 진행률을 반환합니다. "
        "퀘스트에는 plan_id가 없는 독립 일정도 포함됩니다."
    ),
    response_description=(
        "login_id, 전체 quests, 활성 계획의 active_plan_progress"
    ),
)
def get_user_quests(
    login_id: LoginIdPath,
) -> AdminQuestOverviewResponse:
    try:
        return user_admin_service.get_user_quests_by_login_id(login_id)
    except (UserNotFoundError, UserAdminStorageError) as exc:
        _raise_user_http_error(exc)


def _raise_user_http_error(exc: Exception) -> NoReturn:
    if isinstance(exc, UserNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    if isinstance(exc, UserDeleteForbiddenError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=str(exc),
    ) from exc


@user_admin_router.get(
    "",
    response_model=AdminUserListResponse,
    summary="사용자 목록 검색 및 필터 조회",
    description=(
        "로그인 아이디 검색어(search), 역할(role), 활성 상태(is_active)로 사용자를 "
        "필터링하고 페이지 단위로 반환합니다. search는 로그인 아이디 부분 검색이며 "
        "UUID를 입력한 경우 사용자 UUID 정확 검색도 지원합니다."
    ),
    response_description=(
        "items(계정·프로필 목록), page, size, total, total_pages"
    ),
)
def get_users(
    params: Annotated[AdminUserQueryParams, Query()],
) -> AdminUserListResponse:
    try:
        return user_admin_service.get_users(params)
    except UserAdminStorageError as exc:
        _raise_user_http_error(exc)


@user_admin_router.get(
    "/by-login-id/{login_id}",
    response_model=AdminUserDetail,
    summary="로그인 아이디로 사용자 상세 조회",
    description=(
        "회원가입 시 사용한 login_id로 계정 상태, 역할, 경험치, 로그인·잠금 정보와 "
        "취업 프로필·역량 평가 정보를 조회합니다. 비밀번호 해시는 반환하지 않습니다."
    ),
    response_description="사용자 계정 정보와 선택적 profile 상세",
)
def get_user_detail(login_id: LoginIdPath) -> AdminUserDetail:
    try:
        return user_admin_service.get_user_detail_by_login_id(login_id)
    except (UserNotFoundError, UserAdminStorageError) as exc:
        _raise_user_http_error(exc)


@user_admin_router.patch(
    "/{user_id}",
    response_model=AdminUserDetail,
    summary="사용자 활성 상태 수정",
    description=(
        "사용자 UUID로 is_active만 수정합니다. 반환값에는 수정된 계정 정보와 "
        "사용자 프로필이 포함됩니다."
    ),
    response_description="활성 상태가 반영된 사용자 계정·프로필 상세",
)
def update_user(
    user_id: UUID,
    payload: AdminUserUpdate,
) -> AdminUserDetail:
    try:
        return user_admin_service.update_user(user_id, payload)
    except (UserNotFoundError, UserAdminStorageError) as exc:
        _raise_user_http_error(exc)


@user_admin_router.delete(
    "/{user_id}",
    response_model=AdminUserDetail,
    summary="사용자 영구 삭제",
    description=(
        "사용자 UUID로 계정을 영구 삭제하고 삭제 직전 계정 정보를 반환합니다. "
        "삭제 응답의 profile은 null입니다."
    ),
    response_description="삭제된 사용자 계정 정보(profile은 null)",
    responses={
        404: {"description": "삭제할 사용자를 찾을 수 없음"},
        409: {"description": "관리자 역할 계정이어서 삭제할 수 없음"},
        503: {"description": "연관 데이터 또는 계정 삭제 중 DB 작업 실패"},
    },
)
def delete_user(user_id: UUID) -> AdminUserDetail:
    try:
        return user_admin_service.delete_user(user_id)
    except (
        UserDeleteForbiddenError,
        UserNotFoundError,
        UserAdminStorageError,
    ) as exc:
        _raise_user_http_error(exc)
