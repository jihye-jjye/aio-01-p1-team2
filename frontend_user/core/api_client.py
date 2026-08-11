"""프론트엔드에서 공통으로 사용하는 백엔드 HTTP 클라이언트."""

import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

from core.session import clear_auth_state, get_access_token


# frontend_user/.env에 있는 백엔드 주소를 읽습니다.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
BACKEND_URL = os.getenv(
    "BACKEND_URL",
    "https://aio-01-p1-team2-1.onrender.com/api/v1",
).rstrip("/")
REQUEST_TIMEOUT = 60.0

class BackendAPIError(Exception):
    """백엔드 오류 envelope와 네트워크 오류를 동일한 형태로 전달합니다."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.details = details or {}


def _headers(auth_required: bool) -> dict[str, str]:
    """로그인이 필요한 요청이면 access token을 HTTP 헤더에 추가합니다."""

    headers = {"Accept": "application/json"}
    if not auth_required:
        return headers

    token = get_access_token()
    if not token:
        raise BackendAPIError(
            "UNAUTHORIZED",
            "로그인이 필요합니다.",
            status_code=401,
        )

    # 백엔드가 요구하는 JWT 인증 형식입니다.
    headers["Authorization"] = f"Bearer {token}"
    return headers


def request(
    method: str,
    path: str,
    json: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    *,
    auth_required: bool = True,
    clear_auth_on_unauthorized: bool = True,
    timeout: float = REQUEST_TIMEOUT,
) -> Any:
    """요청 성공 시 JSON을, 실패 시 ``BackendAPIError``를 반환합니다."""

    # 페이지마다 httpx 코드를 반복하지 않도록 모든 HTTP 요청을 이 함수가 담당합니다.
    try:
        response = httpx.request(
            method,
            f"{BACKEND_URL}{path}",
            headers=_headers(auth_required),
            json=json,
            data=data,
            files=files,
            params=params,
            timeout=timeout,
        )
    except httpx.TimeoutException as error:
        raise BackendAPIError(
            "CLIENT_TIMEOUT",
            "백엔드 응답 시간이 초과되었습니다.",
            retryable=True,
        ) from error
    except httpx.RequestError as error:
        raise BackendAPIError(
            "NETWORK_ERROR",
            "백엔드 서버에 연결할 수 없습니다.",
            retryable=True,
        ) from error

    # HTTP 상태코드가 200번대이면 정상 응답입니다.
    if response.is_success:
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError as error:
            raise BackendAPIError(
                "INVALID_RESPONSE",
                "백엔드가 올바른 JSON을 반환하지 않았습니다.",
                status_code=response.status_code,
            ) from error

    # 백엔드 오류 응답의 error.code와 message를 꺼냅니다.
    try:
        error_body = response.json().get("error", {})
    except (ValueError, AttributeError):
        error_body = {}

    api_error = BackendAPIError(
        error_body.get("code", "UNKNOWN_ERROR"),
        error_body.get("message", "요청 처리 중 오류가 발생했습니다."),
        status_code=response.status_code,
        retryable=bool(error_body.get("retryable", False)),
        details=error_body.get("details") or {},
    )
    # 401은 토큰이 없거나 만료된 상태이므로 로그인 정보를 삭제합니다.
    if response.status_code == 401 and clear_auth_on_unauthorized:
        clear_auth_state()
    raise api_error
