"""로그인 알림 feed 조회와 알림 확인 처리 API 클라이언트."""

from core.api_client import request


def get_login_notification_feed() -> dict:
    """현재 사용자의 7일 일정과 미확인 알림을 조회합니다."""

    result = request(
        "POST",
        "/notifications/login-feed",
        # 알림 조회 실패만으로 방금 발급받은 로그인 토큰을 폐기하지 않습니다.
        clear_auth_on_unauthorized=False,
    )
    return result if isinstance(result, dict) else {}


def mark_notification_read(notification_id: str) -> dict:
    """사용자가 확인한 알림 한 건을 읽음 상태로 변경합니다."""

    result = request(
        "PATCH",
        f"/notifications/{notification_id}/read",
    )
    return result if isinstance(result, dict) else {}
