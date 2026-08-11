from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any, Literal, Protocol
from uuid import UUID, uuid4

import httpx
from pydantic import ValidationError

from app.notifications.models import (
    DailyTasksPayloadV1,
    LegacyNotificationPayloadV1,
    NotificationFeed,
    NotificationView,
    PlanEndedPayloadV1,
    RoadmapChangePayloadV1,
)


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
    async def login_feed(self) -> dict[str, Any]: ...
    async def mark_notification_read(self, notification_id: str) -> dict[str, Any]: ...
    async def profile(self) -> dict[str, Any]: ...
    async def saved_jobs(self) -> list[dict[str, Any]]: ...
    async def saved_job_recommendation(self) -> dict[str, Any] | None: ...
    async def start_assistant_session(self) -> dict[str, Any]: ...
    async def send_assistant_message(
        self, session_id: str, expected_revision: int, text: str
    ) -> dict[str, Any]: ...
    async def finalize_assistant_session(
        self, session_id: str, expected_revision: int
    ) -> dict[str, Any]: ...
    async def start(self) -> dict[str, Any]: ...
    async def message(self, session_id: str, text: str) -> dict[str, Any]: ...
    async def onboarding_result(self, session_id: str) -> dict[str, Any]: ...
    async def confirm(self, session_id: str, revision: int) -> dict[str, Any]: ...
    async def restart(self, session_id: str) -> dict[str, Any]: ...
    async def create_plan_proposal(
        self, request_id: str, saved_job_id: str | None = None
    ) -> dict[str, Any]: ...
    async def pending_plan_proposal(
        self, start_on: str | None = None, days: int = 7
    ) -> dict[str, Any]: ...
    async def plan_proposal(
        self, proposal_id: str, start_on: str | None = None, days: int = 7
    ) -> dict[str, Any]: ...
    async def accept_plan_proposal(self, proposal_id: str) -> dict[str, Any]: ...
    async def reject_plan_proposal(self, proposal_id: str) -> dict[str, Any]: ...
    async def active_plan(self, start_on: str | None = None, days: int = 7) -> dict[str, Any]: ...
    async def plans_summary(self) -> dict[str, Any]: ...
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
    async def notices(self) -> list[dict[str, Any]]: ...
    async def today_quests(self) -> dict[str, Any]: ...
    async def set_today_quest_status(
        self,
        task_id: str,
        status: Literal["pending", "completed"],
    ) -> dict[str, Any]: ...
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

    async def login_feed(self) -> dict[str, Any]:
        payload = await self._request("POST", "/api/v1/notifications/login-feed")
        if not _valid_notification_feed(payload):
            raise _invalid_notification_response()
        return dict(payload)

    async def mark_notification_read(self, notification_id: str) -> dict[str, Any]:
        payload = await self._request(
            "PATCH",
            f"/api/v1/notifications/{notification_id}/read",
        )
        if (
            not _valid_notification(payload)
            or not _same_uuid(payload.get("id"), notification_id)
            or payload.get("is_read") is not True
            or payload.get("read_at") is None
        ):
            raise _invalid_notification_response()
        return dict(payload)

    async def saved_jobs(self) -> list[dict[str, Any]]:
        payload = await self._request("GET", "/api/v1/saved-jobs")
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise ApiError(502, "INVALID_RESPONSE", "공고 응답 형식을 확인할 수 없습니다.")
        return [dict(item) for item in payload]

    async def saved_job_recommendation(self) -> dict[str, Any] | None:
        payload = await self._request("GET", "/api/v1/saved-jobs/recommendation")
        if payload is None:
            return None
        if not isinstance(payload, dict) or not isinstance(payload.get("job"), dict):
            raise ApiError(502, "INVALID_RESPONSE", "추천 공고 응답 형식을 확인할 수 없습니다.")
        return dict(payload)

    async def start_assistant_session(self) -> dict[str, Any]:
        return await self._state_change(
            "/api/v1/assistant/sessions",
            payload={"request_id": str(uuid4())},
        )

    async def send_assistant_message(
        self,
        session_id: str,
        expected_revision: int,
        text: str,
    ) -> dict[str, Any]:
        return await self._state_change(
            f"/api/v1/assistant/sessions/{session_id}/messages",
            payload={
                "request_id": str(uuid4()),
                "expected_revision": expected_revision,
                "text": text,
            },
        )

    async def finalize_assistant_session(
        self,
        session_id: str,
        expected_revision: int,
    ) -> dict[str, Any]:
        return await self._state_change(
            f"/api/v1/assistant/sessions/{session_id}/finalize",
            payload={
                "request_id": str(uuid4()),
                "expected_revision": expected_revision,
            },
        )

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

    async def onboarding_result(self, session_id: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/api/v1/onboarding/sessions/{session_id}/result",
        )

    async def confirm(self, session_id: str, revision: int) -> dict[str, Any]:
        return await self._state_change(
            f"/api/v1/onboarding/sessions/{session_id}/confirm",
            payload={
                "request_id": str(uuid4()),
                "expected_revision": revision,
            },
        )

    async def restart(self, session_id: str) -> dict[str, Any]:
        return await self._state_change(
            f"/api/v1/onboarding/sessions/{session_id}/messages",
            payload={"request_id": str(uuid4()), "action": "onboarding.restart"},
        )

    async def create_plan_proposal(
        self, request_id: str, saved_job_id: str | None = None
    ) -> dict[str, Any]:
        payload = {"request_id": request_id}
        if saved_job_id is not None:
            payload["saved_job_id"] = saved_job_id
        return await self._state_change(
            "/api/v1/plan-proposals",
            payload=payload,
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

    async def plans_summary(self) -> dict[str, Any]:
        return await self._request("GET", "/api/v1/plans/summary")

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

    async def notices(self) -> list[dict[str, Any]]:
        payload = await self._request("GET", "/api/v1/notices")
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise ApiError(502, "INVALID_RESPONSE", "공지 응답 형식을 확인할 수 없습니다.")
        return [dict(item) for item in payload]

    async def today_quests(self) -> dict[str, Any]:
        return await self._request("GET", "/api/v1/quests/today")

    async def set_today_quest_status(
        self,
        task_id: str,
        status: Literal["pending", "completed"],
    ) -> dict[str, Any]:
        return await self._request(
            "PATCH",
            f"/api/v1/quests/{task_id}",
            json={"status": status},
        )

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
            try:
                return response.json()
            except ValueError as exc:
                raise ApiError(
                    502,
                    "INVALID_RESPONSE",
                    "서버 응답 형식을 확인할 수 없습니다.",
                ) from exc
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


def _invalid_notification_response() -> ApiError:
    return ApiError(502, "INVALID_RESPONSE", "알림 응답 형식을 확인할 수 없습니다.")


def _valid_notification_feed(value: object) -> bool:
    try:
        feed = NotificationFeed.model_validate_json(
            json.dumps(value, ensure_ascii=False),
            strict=True,
        )
    except (TypeError, ValueError, ValidationError):
        return False
    if feed.window_end != feed.window_start + timedelta(days=6):
        return False
    returned_count = len(feed.upcoming) + len(feed.changes)
    if feed.unread_count < returned_count:
        return False
    section_may_be_truncated = len(feed.upcoming) == 7 or len(feed.changes) == 50
    if not section_may_be_truncated and feed.unread_count != returned_count:
        return False
    if not all(_valid_parsed_notification(item) and not item.is_read for item in feed.upcoming):
        return False
    if not all(_valid_parsed_notification(item) and not item.is_read for item in feed.changes):
        return False
    if any(item.type != "daily_tasks" for item in feed.upcoming):
        return False
    if any(item.type == "daily_tasks" for item in feed.changes):
        return False

    upcoming_dates = [
        item.payload.date for item in feed.upcoming if isinstance(item.payload, DailyTasksPayloadV1)
    ]
    if len(upcoming_dates) != len(feed.upcoming):
        return False
    if upcoming_dates != sorted(upcoming_dates):
        return False
    if any(
        item_date < feed.window_start or item_date > feed.window_end for item_date in upcoming_dates
    ):
        return False
    change_times = [item.available_at for item in feed.changes]
    return change_times == sorted(change_times, reverse=True)


def _valid_notification(value: object) -> bool:
    try:
        notification = NotificationView.model_validate_json(
            json.dumps(value, ensure_ascii=False),
            strict=True,
        )
    except (TypeError, ValueError, ValidationError):
        return False
    return _valid_parsed_notification(notification)


def _same_uuid(left: object, right: object) -> bool:
    try:
        return UUID(str(left)) == UUID(str(right))
    except (TypeError, ValueError):
        return False


def _valid_parsed_notification(notification: NotificationView) -> bool:
    if notification.is_read != (notification.read_at is not None):
        return False
    if not _aware_datetime(notification.available_at):
        return False
    if notification.read_at is not None and not _aware_datetime(notification.read_at):
        return False
    payload = notification.payload
    if notification.type == "daily_tasks":
        return isinstance(payload, DailyTasksPayloadV1) and all(
            _aware_datetime(schedule.scheduled_at) for schedule in payload.schedules
        )
    if notification.type == "roadmap_changed":
        return isinstance(payload, RoadmapChangePayloadV1)
    if notification.type == "plan_ended":
        return isinstance(payload, PlanEndedPayloadV1)
    return isinstance(payload, LegacyNotificationPayloadV1)


def _aware_datetime(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None
