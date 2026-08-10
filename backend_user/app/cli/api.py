from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, Protocol
from uuid import uuid4

import httpx


class ApiError(RuntimeError):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.retryable = retryable


class ApiPort(Protocol):
    async def signup(self, login_id: str, login_pw: str, user_name: str) -> str: ...
    async def login(self, login_id: str, login_pw: str) -> None: ...
    async def profile(self) -> dict[str, Any]: ...
    async def start(self) -> dict[str, Any]: ...
    async def message(self, session_id: str, text: str) -> dict[str, Any]: ...
    async def confirm(self, session_id: str, revision: int) -> dict[str, Any]: ...
    async def restart(self, session_id: str) -> dict[str, Any]: ...
    async def create_plan_proposal(self, request_id: str) -> dict[str, Any]: ...
    async def pending_plan_proposal(
        self, start_on: str | None = None, days: int = 7
    ) -> dict[str, Any]: ...
    async def plan_proposal(
        self, proposal_id: str, start_on: str | None = None, days: int = 7
    ) -> dict[str, Any]: ...
    async def accept_plan_proposal(self, proposal_id: str) -> dict[str, Any]: ...
    async def reject_plan_proposal(self, proposal_id: str) -> dict[str, Any]: ...
    async def active_plan(self, start_on: str | None = None, days: int = 7) -> dict[str, Any]: ...
    async def plan(
        self, plan_id: str, start_on: str | None = None, days: int = 7
    ) -> dict[str, Any]: ...
    async def set_plan_task_status(
        self,
        plan_id: str,
        task_id: str,
        status: Literal["pending", "completed"],
    ) -> dict[str, Any]: ...
    async def complete_plan(self, plan_id: str) -> dict[str, Any]: ...
    def clear_access_token(self) -> None: ...
    async def aclose(self) -> None: ...


class CoachApiClient:
    def __init__(
        self,
        *,
        base_url: str = "http://192.100.200.209:8010",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client = client or httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(300, connect=10),
        )
        self._owns_client = client is None
        self._access_token: str | None = None

    async def login(self, login_id: str, login_pw: str) -> None:
        payload = await self._request(
            "POST",
            "/api/v1/auth/login",
            json={"login_id": login_id, "login_pw": login_pw},
            authenticated=False,
        )
        self._access_token = payload["access_token"]

    async def signup(self, login_id: str, login_pw: str, user_name: str) -> str:
        payload = await self._request(
            "POST",
            "/api/v1/auth/signup",
            json={"login_id": login_id, "login_pw": login_pw, "user_name": user_name},
            authenticated=False,
        )
        self._access_token = payload["access_token"]
        return str(payload["login_id"])

    async def profile(self) -> dict[str, Any]:
        return await self._request("GET", "/api/v1/profile")

    def clear_access_token(self) -> None:
        self._access_token = None

    async def start(self) -> dict[str, Any]:
        return await self._state_change(
            "/api/v1/onboarding/sessions",
            payload={"request_id": str(uuid4())},
        )

    async def message(self, session_id: str, text: str) -> dict[str, Any]:
        return await self._state_change(
            f"/api/v1/onboarding/sessions/{session_id}/messages",
            payload={"request_id": str(uuid4()), "text": text},
        )

    async def confirm(self, session_id: str, revision: int) -> dict[str, Any]:
        return await self._state_change(
            f"/api/v1/onboarding/sessions/{session_id}/messages",
            payload={
                "request_id": str(uuid4()),
                "action": "onboarding.confirm",
                "expected_revision": revision,
            },
        )

    async def restart(self, session_id: str) -> dict[str, Any]:
        return await self._state_change(
            f"/api/v1/onboarding/sessions/{session_id}/messages",
            payload={"request_id": str(uuid4()), "action": "onboarding.restart"},
        )

    async def create_plan_proposal(self, request_id: str) -> dict[str, Any]:
        return await self._state_change(
            "/api/v1/plan-proposals",
            payload={"request_id": request_id},
        )

    async def pending_plan_proposal(
        self, start_on: str | None = None, days: int = 7
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/api/v1/plan-proposals/pending",
            params=self._window_params(start_on=start_on, days=days),
        )

    async def plan_proposal(
        self,
        proposal_id: str,
        start_on: str | None = None,
        days: int = 7,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/api/v1/plan-proposals/{proposal_id}",
            params=self._window_params(start_on=start_on, days=days),
        )

    async def accept_plan_proposal(self, proposal_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/api/v1/plan-proposals/{proposal_id}/accept")

    async def reject_plan_proposal(self, proposal_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/api/v1/plan-proposals/{proposal_id}/reject")

    async def active_plan(self, start_on: str | None = None, days: int = 7) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/api/v1/plans/active",
            params=self._window_params(start_on=start_on, days=days),
        )

    async def plan(
        self,
        plan_id: str,
        start_on: str | None = None,
        days: int = 7,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/api/v1/plans/{plan_id}",
            params=self._window_params(start_on=start_on, days=days),
        )

    async def set_plan_task_status(
        self,
        plan_id: str,
        task_id: str,
        status: Literal["pending", "completed"],
    ) -> dict[str, Any]:
        return await self._request(
            "PATCH",
            f"/api/v1/plans/{plan_id}/tasks/{task_id}",
            json={"status": status},
        )

    async def complete_plan(self, plan_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/api/v1/plans/{plan_id}/complete")

    @staticmethod
    def _window_params(*, start_on: str | None, days: int) -> dict[str, str | int]:
        if start_on is None:
            return {"days": days}
        return {"start_on": start_on, "days": days}

    async def _state_change(
        self,
        path: str,
        *,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        for attempt in range(2):
            try:
                return await self._request("POST", path, json=payload)
            except ApiError as exc:
                if attempt == 1 or exc.code not in {
                    "CLIENT_TIMEOUT",
                    "CLIENT_NETWORK_ERROR",
                }:
                    raise
        raise RuntimeError("도달할 수 없는 CLI 재시도 상태입니다.")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: Mapping[str, str | int] | None = None,
        authenticated: bool = True,
    ) -> dict[str, Any]:
        headers: dict[str, str] = {}
        if authenticated:
            if self._access_token is None:
                raise ApiError(401, "UNAUTHORIZED", "로그인이 필요합니다.")
            headers["Authorization"] = f"Bearer {self._access_token}"
        try:
            request_kwargs: dict[str, Any] = {"headers": headers}
            if json is not None:
                request_kwargs["json"] = json
            if params is not None:
                request_kwargs["params"] = params
            response = await self._client.request(method, path, **request_kwargs)
        except httpx.TimeoutException as exc:
            raise ApiError(
                503, "CLIENT_TIMEOUT", "서버 응답 시간이 초과되었습니다.", retryable=True
            ) from exc
        except httpx.HTTPError as exc:
            raise ApiError(
                503, "CLIENT_NETWORK_ERROR", "서버에 연결할 수 없습니다.", retryable=True
            ) from exc
        if response.is_success:
            return response.json()
        error = _parse_api_error(response)
        raise ApiError(
            response.status_code,
            error["code"],
            error["message"],
            retryable=error["retryable"],
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def _parse_api_error(response: httpx.Response) -> dict[str, str | bool]:
    try:
        body = response.json()
    except ValueError:
        body = None
    error = body.get("error") if isinstance(body, Mapping) else None
    if not isinstance(error, Mapping):
        return {
            "code": "API_ERROR",
            "message": "요청을 처리하지 못했습니다.",
            "retryable": False,
        }
    code = error.get("code")
    message = error.get("message")
    retryable = error.get("retryable")
    return {
        "code": code if isinstance(code, str) else "API_ERROR",
        "message": message if isinstance(message, str) else "요청을 처리하지 못했습니다.",
        "retryable": retryable if isinstance(retryable, bool) else False,
    }
