"""오늘 할 일 조회와 완료 상태 변경 API를 관리합니다."""

from core.api_client import request


def get_today_quests() -> dict:
    """로그인한 사용자의 오늘 할 일 목록을 조회합니다."""

    return request("GET", "/quests/today")


def update_today_quest(task_id: str, status: str) -> dict:
    """오늘 할 일을 완료하거나 완료 전 상태로 되돌립니다."""

    return request(
        "PATCH",
        f"/quests/{task_id}",
        json={"status": status},
    )
