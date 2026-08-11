"""AI 채팅 시작 답변, 확정, 재시작 API."""

from uuid import uuid4

from core.api_client import request


def _pending(path: str, body: dict) -> dict:
    """네트워크 실패 시 같은 요청을 다시 보낼 수 있도록 요청 정보를 보관합니다."""

    return {"requestId": body["request_id"], "path": path, "body": body}


def start_onboarding() -> tuple[dict, dict]:
    """새 AI 프로필 분석 세션을 시작하고 첫 질문을 받습니다."""

    path = "/onboarding/sessions"
    body = {"request_id": str(uuid4())}
    pending = _pending(path, body)
    return request("POST", path, json=body), pending


def send_message(session_id: str, text: str) -> tuple[dict, dict]:
    """사용자의 답변 또는 프로필 수정 요청을 전송합니다."""

    path = f"/onboarding/sessions/{session_id}/messages"
    body = {"request_id": str(uuid4()), "text": text}
    pending = _pending(path, body)
    return request("POST", path, json=body), pending


def confirm_onboarding(
    session_id: str,
    expected_revision: int,
) -> tuple[dict, dict]:
    """검토 화면의 최신 revision을 사용해 프로필 저장을 확정합니다."""

    path = f"/onboarding/sessions/{session_id}/messages"
    body = {
        "request_id": str(uuid4()),
        "action": "onboarding.confirm",
        "expected_revision": expected_revision,
    }
    pending = _pending(path, body)
    return request("POST", path, json=body), pending


def restart_onboarding(session_id: str) -> tuple[dict, dict]:
    """현재 세션을 유지하면서 질문 진행 상태를 처음으로 되돌립니다."""

    path = f"/onboarding/sessions/{session_id}/messages"
    body = {"request_id": str(uuid4()), "action": "onboarding.restart"}
    pending = _pending(path, body)
    return request("POST", path, json=body), pending


def retry_pending(pending: dict) -> dict:
    """재시도는 새 UUID를 만들지 않고 기존 path/body를 그대로 사용합니다."""

    return request("POST", pending["path"], json=pending["body"])
