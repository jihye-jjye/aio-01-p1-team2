"""저장 공고와 사용자 맞춤 추천 공고 API를 호출합니다."""

from core.api_client import request


def get_saved_jobs() -> list[dict]:
    """팀에서 저장한 전체 채용 공고를 최신순으로 불러옵니다."""
    result = request("GET", "/saved-jobs")
    return result if isinstance(result, list) else []


def get_recommended_job() -> dict | None:
    """희망 근무 환경과 가장 가까운 공고 한 건을 불러옵니다."""
    result = request("GET", "/saved-jobs/recommendation")
    return result if isinstance(result, dict) else None
