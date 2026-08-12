"""모든 메뉴 API에서 공통으로 사용하는 HTTP 요청 기능."""

import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from streamlit_session_browser_storage import SessionStorage

BACKEND_USER_URL = "https://aio-01-p1-team2-1.onrender.com/api/v1"
BACKEND_ADMIN_URL = "https://aio-01-p1-team2.onrender.com/api/v1"

REQUEST_TIMEOUT = 60.0

class BackendAPIError(Exception):
    """백엔드 연결 또는 API 응답 처리 중 발생한 오류입니다."""

def request(
    method: str,
    path: str,
    json: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    role: str | None = None,
    auth_required: bool = True,
) -> Any:
    """선택한 백엔드로 요청z하고 JSON 응답을 반환합니다."""
    storage = SessionStorage()
    if role == "ADMIN":
        backend_url = BACKEND_ADMIN_URL
    else :
        backend_url = BACKEND_USER_URL

    # normalized_path = f"/{path.lstrip('/')}"
    headers: dict[str, str] = {}

    if auth_required:        
        token = storage.getItem("access_token") or ""
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = httpx.request(
            method,
            f"{backend_url}{path}",
            json=json,
            data=data,
            files=files,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
    except httpx.TimeoutException as error:
        raise BackendAPIError("백엔드 응답 시간이 초과되었습니다.") from error
    except httpx.RequestError as error:
        raise BackendAPIError(
            "백엔드 서버에 연결할 수 없습니다. 서버 실행 상태를 확인해 주세요."
        ) from error

    if not 200 <= response.status_code < 300:
        raise BackendAPIError(
            f"백엔드 요청 실패 (HTTP {response.status_code}): "
        )

    if response.status_code == 204 or not response.content:
        return None

    try:
        return response.json()
    except ValueError as error:
        raise BackendAPIError("백엔드가 올바른 JSON을 반환하지 않았습니다.") from error