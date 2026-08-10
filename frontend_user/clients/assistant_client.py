"""AI 상담 백엔드 API 클라이언트.

화면에서는 Streamlit 상태와 렌더링만 담당하고, 요청 형태와 응답 검증은
이 모듈에서 관리합니다. CHAT_ENDPOINT는 백엔드 최종 계약에 맞춰 조정합니다.
"""

from typing import Any
from uuid import uuid4

from core.api_client import BackendAPIError, request


# 백엔드 Swagger의 최종 주소가 달라지면 아래 상수만 수정하면 됩니다.
CHAT_ENDPOINT = "/chat/gemini"
SESSION_ENDPOINT = "/assistant/sessions"
CHAT_TIMEOUT = 30.0
ALLOWED_ROLES = {"user", "assistant"}


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
        raise BackendAPIError(
            "INVALID_RESPONSE",
            "AI 상담 세션 응답 형식이 올바르지 않습니다.",
        )
    if not isinstance(result.get("session_id"), str):
        raise BackendAPIError(
            "INVALID_RESPONSE",
            "AI 상담 세션 ID가 없습니다.",
        )
    if not isinstance(result.get("assistant_message"), str):
        raise BackendAPIError(
            "INVALID_RESPONSE",
            "AI 상담 시작 메시지가 없습니다.",
        )
    return result


def build_chat_history(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    """화면 메시지 중 백엔드에 전달 가능한 역할과 문자열만 추출합니다."""

    # 버튼 상태 같은 화면용 데이터는 제외하고 role/content만 백엔드에 전달합니다.
    history: list[dict[str, str]] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role not in ALLOWED_ROLES or not isinstance(content, str):
            continue
        history.append({"role": role, "content": content})
    return history


def send_chat_message(
    question: str,
    messages: list[dict[str, Any]],
) -> str:
    """질문과 이전 대화를 전송하고 검증된 AI 답변 문자열을 반환합니다."""

    # 질문 앞뒤의 실수로 입력한 공백만 제거합니다.
    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("질문을 입력해 주세요.")

    # 현재 질문은 question에 별도로 전달하므로 history에 중복 포함하지 않습니다.
    result = request(
        "POST",
        CHAT_ENDPOINT,
        json={
            "question": normalized_question,
            "messages": build_chat_history(messages),
        },
        auth_required=True,
        timeout=CHAT_TIMEOUT,
    )

    if not isinstance(result, dict) or not isinstance(result.get("answer"), str):
        raise BackendAPIError(
            "INVALID_RESPONSE",
            "AI 상담 응답 형식이 올바르지 않습니다.",
        )
    return result["answer"]
