"""AI 취업 코치의 세션 시작, 메시지 전송, 상담 종료 API 클라이언트."""

from typing import Any
from uuid import uuid4

from core.api_client import BackendAPIError, request


SESSION_ENDPOINT = "/assistant/sessions"
ASSISTANT_TIMEOUT = 120.0


def _validate_response(result: object, required_fields: tuple[str, ...]) -> dict[str, Any]:
    """상담 API의 필수 응답 필드가 있는지 확인합니다."""

    if not isinstance(result, dict):
        raise BackendAPIError(
            "INVALID_RESPONSE",
            "AI 상담 응답 형식이 올바르지 않습니다.",
        )
    for field in required_fields:
        if field not in result:
            raise BackendAPIError(
                "INVALID_RESPONSE",
                f"AI 상담 응답에 {field} 값이 없습니다.",
            )
    return result


def start_assistant_session(request_id: str | None = None) -> dict[str, Any]:
    """완성된 취업 프로필을 기준으로 새 AI 상담 세션을 생성합니다."""

    result = request(
        "POST",
        SESSION_ENDPOINT,
        json={"request_id": request_id or str(uuid4())},
        timeout=ASSISTANT_TIMEOUT,
    )
    return _validate_response(
        result,
        ("session_id", "revision", "assistant_message", "expires_at"),
    )


def send_assistant_message(
    session_id: str,
    expected_revision: int,
    text: str,
    request_id: str | None = None,
) -> dict[str, Any]:
    """현재 revision과 사용자 질문을 보내고 AI 답변을 받습니다."""

    result = request(
        "POST",
        f"{SESSION_ENDPOINT}/{session_id}/messages",
        json={
            "request_id": request_id or str(uuid4()),
            "expected_revision": expected_revision,
            "text": text,
        },
        timeout=ASSISTANT_TIMEOUT,
    )
    return _validate_response(
        result,
        ("session_id", "revision", "assistant_message", "expires_at"),
    )


def finalize_assistant_session(
    session_id: str,
    expected_revision: int,
    request_id: str | None = None,
) -> dict[str, Any]:
    """현재 상담을 보고서로 저장하고 대화 세션을 종료합니다."""

    result = request(
        "POST",
        f"{SESSION_ENDPOINT}/{session_id}/finalize",
        json={
            "request_id": request_id or str(uuid4()),
            "expected_revision": expected_revision,
        },
        timeout=ASSISTANT_TIMEOUT,
    )
    return _validate_response(
        result,
        ("ai_result_id", "session_id", "session_revision", "report"),
    )
