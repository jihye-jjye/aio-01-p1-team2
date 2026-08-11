"""AI 상담 백엔드 API 클라이언트.

화면에서는 Streamlit 상태와 렌더링만 담당하고, 요청 형태와 응답 검증은
이 모듈에서 관리합니다.
"""

from typing import Any
from uuid import UUID, uuid4

from core.api_client import BackendAPIError, request

SESSION_ENDPOINT = "/assistant/sessions"
CHAT_TIMEOUT = 30.0
ALLOWED_ROLES = {"user", "assistant"}


def _invalid_response(message: str) -> BackendAPIError:
    return BackendAPIError("INVALID_RESPONSE", message)


def build_chat_history(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    """이전 ``chat_client`` import 경로를 위한 대화 필터 호환 함수를 제공합니다."""

    history: list[dict[str, str]] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role not in ALLOWED_ROLES or not isinstance(content, str):
            continue
        history.append({"role": role, "content": content})
    return history


def start_assistant_session() -> dict[str, Any]:
    """AI 상담 세션을 생성하고 백엔드의 시작 메시지를 반환합니다."""

    result = request(
        "POST",
        SESSION_ENDPOINT,
        json={"request_id": str(uuid4())},
        auth_required=True,
        timeout=CHAT_TIMEOUT,
    )
    if not isinstance(result, dict):
        raise _invalid_response("AI 상담 세션 응답 형식이 올바르지 않습니다.")

    session_id = result.get("session_id")
    assistant_message = result.get("assistant_message")
    if not isinstance(session_id, str) or not session_id.strip():
        raise _invalid_response("AI 상담 세션 ID가 없습니다.")
    if result.get("revision") != 0:
        raise _invalid_response("AI 상담 세션 revision이 올바르지 않습니다.")
    if not isinstance(assistant_message, str) or not assistant_message.strip():
        raise _invalid_response("AI 상담 시작 메시지가 없습니다.")

    validated = dict(result)
    validated["session_id"] = session_id.strip()
    validated["assistant_message"] = assistant_message.strip()
    return validated


def send_chat_message(
    session_id: str,
    expected_revision: int,
    text: str,
    *,
    request_id: str | None = None,
) -> dict[str, Any]:
    """상담 메시지를 전송하고 세션·revision이 일치하는 응답을 반환합니다."""

    normalized_session_id = session_id.strip() if isinstance(session_id, str) else ""
    if not normalized_session_id:
        raise ValueError("AI 상담 세션이 없습니다.")
    if (
        not isinstance(expected_revision, int)
        or isinstance(expected_revision, bool)
        or expected_revision < 0
    ):
        raise ValueError("AI 상담 revision이 올바르지 않습니다.")

    normalized_text = text.strip() if isinstance(text, str) else ""
    if not normalized_text:
        raise ValueError("질문을 입력해 주세요.")

    if request_id is None:
        message_request_id = str(uuid4())
    else:
        try:
            message_request_id = str(UUID(request_id))
        except (TypeError, ValueError, AttributeError) as error:
            raise ValueError("request_id는 UUID 형식이어야 합니다.") from error
    result = request(
        "POST",
        f"{SESSION_ENDPOINT}/{normalized_session_id}/messages",
        json={
            "request_id": message_request_id,
            "expected_revision": expected_revision,
            "text": normalized_text,
        },
        auth_required=True,
        timeout=CHAT_TIMEOUT,
    )

    if not isinstance(result, dict):
        raise _invalid_response("AI 상담 응답 형식이 올바르지 않습니다.")

    response_session_id = result.get("session_id")
    response_revision = result.get("revision")
    assistant_message = result.get("assistant_message")
    if response_session_id != normalized_session_id:
        raise _invalid_response("AI 상담 응답의 세션 ID가 일치하지 않습니다.")
    if response_revision != expected_revision + 1:
        raise _invalid_response("AI 상담 응답의 revision이 올바르지 않습니다.")
    if not isinstance(assistant_message, str) or not assistant_message.strip():
        raise _invalid_response("AI 상담 답변이 없습니다.")

    validated = dict(result)
    validated["assistant_message"] = assistant_message.strip()
    return validated
