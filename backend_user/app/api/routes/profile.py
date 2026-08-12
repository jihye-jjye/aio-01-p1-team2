from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import ProfileReader, get_current_user, get_profile_reader
from app.api.errors import APIErrorEnvelope, ProfileNotFoundError
from app.auth.models import CurrentUser
from app.profiles.models import ProfileRecord

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get(
    "",
    response_model=ProfileRecord,
    summary="확정 저장된 프로필 조회",
    description="""
현재 인증 사용자의 온보딩 완료 프로필과 준비도 평가 출처를 PostgreSQL에서 조회합니다.

- 로그인 직후 이 API를 호출해 `200`이면 기존 프로필 화면으로 이동합니다.
- `PROFILE_NOT_FOUND`이면 아직 확정 저장된 프로필이 없으므로 온보딩을 시작합니다.
- 응답에는 8개 프로필 필드, assessment 결과, `assessment_result_id`,
  `draft_revision`, `snapshot_hash`, provider/model/prompt/rubric version이 포함됩니다.
- 온보딩 confirm 성공 후 이 API를 다시 호출해 review/completed snapshot과 영속 결과를 대조합니다.
- 사용자 ID는 Bearer access token에서만 결정합니다.
""",
    response_description="확정 프로필과 추적 가능한 준비도 평가 정보",
    responses={
        401: {
            "model": APIErrorEnvelope,
            "description": "`UNAUTHORIZED`: Bearer token 없음, 만료 또는 검증 실패",
        },
        404: {
            "model": APIErrorEnvelope,
            "description": "`PROFILE_NOT_FOUND`: 확정 저장된 프로필 없음",
        },
        503: {
            "model": APIErrorEnvelope,
            "description": "`SERVICE_UNAVAILABLE`: PostgreSQL 장애",
        },
    },
)
async def get_profile(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    profiles: Annotated[ProfileReader, Depends(get_profile_reader)],
) -> ProfileRecord:
    profile = await profiles.get_by_user_id(current_user.id)
    if profile is None:
        raise ProfileNotFoundError
    return profile
