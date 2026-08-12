"""모든 메뉴 API에서 공통으로 사용하는 HTTP 요청 기능."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DEFAULT_BACKEND_USER_URL = "https://aio-01-p1-team2-1.onrender.com/api/v1"
DEFAULT_BACKEND_ADMIN_URL = "https://aio-01-p1-team2.onrender.com/api/v1"

BACKEND_USER_URL = (
    os.getenv("BACKEND_USER_URL") or DEFAULT_BACKEND_USER_URL
).rstrip("/")
BACKEND_ADMIN_URL = (
    os.getenv("BACKEND_ADMIN_URL") or DEFAULT_BACKEND_ADMIN_URL
).rstrip("/")
REQUEST_TIMEOUT = 60.0


class BackendAPIError(Exception):
    """백엔드 연결 또는 API 응답 처리 중 발생한 오류입니다."""


def _backend_url_for(role: str | None) -> str:
    if role in (None, "USER"):
        return BACKEND_USER_URL.rstrip("/")
    if role == "ADMIN":
        return BACKEND_ADMIN_URL.rstrip("/")
    raise BackendAPIError(f"지원하지 않는 백엔드 역할입니다: {role}")


def _error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip() or "오류 상세 정보가 없습니다."

    if isinstance(payload, dict):
        detail = payload.get("detail") or payload.get("message")
        if isinstance(detail, list):
            messages = [
                item.get("msg", str(item)) if isinstance(item, dict) else str(item)
                for item in detail
            ]
            return "; ".join(messages)
        if detail:
            return str(detail)

    return str(payload)


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
    """선택한 백엔드로 요청하고 JSON 응답을 반환합니다."""

    backend_url = _backend_url_for(role)
    normalized_path = f"/{path.lstrip('/')}"
    headers: dict[str, str] = {}

    if auth_required:
        token = getattr(st.session_state, "access_token", "")
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = httpx.request(
            method,
            f"{backend_url}{normalized_path}",
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
            f"{_error_detail(response)}"
        )

    if response.status_code == 204 or not response.content:
        return None

    try:
        return response.json()
    except ValueError as error:
        raise BackendAPIError("백엔드가 올바른 JSON을 반환하지 않았습니다.") from error
