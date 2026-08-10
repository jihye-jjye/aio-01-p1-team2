"""계획 제안과 활성 로드맵 API 호출을 한곳에서 관리합니다."""

from core.api_client import request


def create_plan_proposal(request_id: str) -> dict:
    """확정된 프로필을 기준으로 AI 계획 제안을 생성합니다."""

    return request(
        "POST",
        "/plan-proposals",
        json={"request_id": request_id},
        timeout=120.0,
    )


def get_pending_proposal(start_on: str | None = None, days: int = 7) -> dict:
    """사용자가 아직 결정하지 않은 계획 제안을 조회합니다."""

    params = {"days": days}
    if start_on:
        params["start_on"] = start_on
    return request("GET", "/plan-proposals/pending", params=params)


def accept_proposal(proposal_id: str) -> dict:
    """계획 제안을 수락하고 활성 계획을 생성합니다."""

    return request("POST", f"/plan-proposals/{proposal_id}/accept")


def reject_proposal(proposal_id: str) -> dict:
    """계획 제안을 거절합니다."""

    return request("POST", f"/plan-proposals/{proposal_id}/reject")


def get_active_plan(start_on: str | None = None, days: int = 7) -> dict:
    """활성 계획의 지정 날짜 구간을 조회합니다."""

    params = {"days": days}
    if start_on:
        params["start_on"] = start_on
    return request("GET", "/plans/active", params=params)


def update_task_status(plan_id: str, task_id: str, status: str) -> dict:
    """활성 계획의 미션을 완료하거나 완료 취소합니다."""

    return request(
        "PATCH",
        f"/plans/{plan_id}/tasks/{task_id}",
        json={"status": status},
    )


def complete_plan(plan_id: str) -> dict:
    """모든 미션이 완료된 활성 계획을 종료합니다."""

    return request("POST", f"/plans/{plan_id}/complete")
