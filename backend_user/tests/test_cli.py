import asyncio
import os
import select
import signal
import sys
import time
from collections import deque
from copy import deepcopy
from io import StringIO
from typing import Any
from uuid import UUID

import pytest
from rich.console import Console

from app.cli.api import ApiError
from app.cli.app import (
    CliApp,
    TerminalInput,
    _active_matches_proposal,
    _completion_matches_review,
    _visible_task_selections,
)
from app.cli.renderer import RichRenderer

try:
    import pty
    import termios
except ImportError:  # pragma: no cover - exercised by collection on non-POSIX systems
    pty = None  # type: ignore[assignment]
    termios = None  # type: ignore[assignment]

FIELDS = (
    "target_role",
    "skills",
    "experience_summary",
    "target_date",
    "target_company",
    "preferred_environment",
    "daily_notification_time",
    "assistant_style",
)
SESSION_ID = "10000000-0000-0000-0000-000000000001"
RESULT_ID = "40000000-0000-0000-0000-000000000001"

PROFILE = {
    "user_id": "00000000-0000-0000-0000-000000000001",
    "target_role": "백엔드 개발자",
    "skills": ["Python", "FastAPI"],
    "experience_summary": "팀 프로젝트에서 API를 배포했습니다.",
    "target_date": "2026-11-08",
    "target_company": None,
    "preferred_environment": "원격 근무와 코드 리뷰",
    "daily_notification_time": "09:30:00",
    "assistant_style": "friendly",
    "assessment_score": 66,
    "assessment_level": "intermediate",
    "assessment_summary": {
        "dimensions": {
            "skill_readiness": {"score": 22, "reason": "기술 근거"},
            "experience_depth": {"score": 18, "reason": "경험 근거"},
            "goal_clarity": {"score": 14, "reason": "목표 근거"},
            "execution_readiness": {"score": 12, "reason": "실행 근거"},
        }
    },
    "assessment_version": "onboarding-assessment-v2",
    "assessment_result_id": RESULT_ID,
    "draft_revision": 4,
    "snapshot_hash": "a" * 64,
    "assessment_source": {
        "provider": "google",
        "model": "gemini-3.6-flash",
        "prompt_version": "onboarding-assessment-v2",
        "rubric_version": "assessment-rubric-v2",
    },
    "access_token": "must-not-print",
}

EMPTY_PAYLOAD = {
    "draft_revision": 0,
    "draft_profile": {},
    "answered_fields": [],
    "missing_fields": list(FIELDS),
    "assessment": None,
    "engine": {
        "provider": "google",
        "model": "gemini-3.6-flash",
        "api_version": "v1",
        "mode": "live",
        "conversation_prompt_version": "onboarding-conversation-v1",
        "assessment_prompt_version": "onboarding-assessment-v2",
        "api_key": "must-not-print",
    },
    "stored_profile": None,
}

ASSESSMENT = {
    "score": 66,
    "level": "intermediate",
    "summary": deepcopy(PROFILE["assessment_summary"]),
    "version": "onboarding-assessment-v2",
    "model_name": "gemini-3.6-flash",
    "provider": "google",
    "prompt_version": "onboarding-assessment-v2",
    "rubric_version": "assessment-rubric-v2",
    "schema_version": "profile-assessment-v1",
}

REVIEW_PAYLOAD = {
    **deepcopy(EMPTY_PAYLOAD),
    "draft_revision": 4,
    "draft_profile": {field: PROFILE[field] for field in FIELDS},
    "answered_fields": list(FIELDS),
    "missing_fields": [],
    "assessment": deepcopy(ASSESSMENT),
}


def response(step: str, payload: dict[str, Any], message: str) -> dict[str, Any]:
    return {
        "session_id": SESSION_ID,
        "flow": "onboarding",
        "step": step,
        "assistant_message": message,
        "choices": [],
        "payload": deepcopy(payload),
        "completed": step == "completed",
        "provider_raw_response": "must-not-print",
    }


START = response("conversation", EMPTY_PAYLOAD, "준비 중인 직무를 알려주세요.")
REVIEW = response("review", REVIEW_PAYLOAD, "정보를 정리했습니다. 검토해주세요.")
COMPLETED = response(
    "completed",
    {**REVIEW_PAYLOAD, "stored_profile": PROFILE},
    "저장했습니다.",
)

PROPOSAL_ID = "50000000-0000-0000-0000-000000000001"
PLAN_ID = "60000000-0000-0000-0000-000000000001"
TASK_ID_1 = "70000000-0000-0000-0000-000000000001"
TASK_ID_2 = "70000000-0000-0000-0000-000000000002"

SAVED_JOBS = [
    {
        "id": "90000000-0000-0000-0000-000000000001",
        "source_type": "url",
        "source_url": "https://example.com/jobs/backend",
        "source_key": "example-backend-2026",
        "company_name": "예시회사",
        "job_title": "백엔드 개발자",
        "deadline": "2026-08-31",
        "posting_text": "Python과 FastAPI 경험자를 찾습니다.",
        "extracted_data": {"skills": ["Python", "FastAPI"]},
        "created_at": "2026-08-10T09:00:00+09:00",
        "updated_at": "2026-08-10T09:00:00+09:00",
    }
]
SAVED_JOB_RECOMMENDATION = {
    "preferred_environment": "원격 근무와 코드 리뷰",
    "match_score": 100,
    "matched_terms": ["원격", "코드", "리뷰"],
    "recommendation_source": "llm",
    "reason": "전체 프로필과 가장 잘 맞는 공고입니다.",
    "job": deepcopy(SAVED_JOBS[0]),
}

ASSISTANT_SESSION_ID = "a0000000-0000-0000-0000-000000000001"
ASSISTANT_START = {
    "session_id": ASSISTANT_SESSION_ID,
    "revision": 0,
    "assistant_style": "friendly",
    "assistant_message": "반가워요. 취업 고민을 알려주세요.",
    "expires_at": "2026-08-12T10:00:00+09:00",
}
ASSISTANT_MESSAGE = {
    "session_id": ASSISTANT_SESSION_ID,
    "revision": 1,
    "intent": "general",
    "assistant_message": "[bold]지원 근거[/bold]를 먼저 정리해보세요.",
    "tool_results": [],
    "coaching": None,
    "expires_at": "2026-08-12T10:00:00+09:00",
}
ASSISTANT_REPORT = {
    "ai_result_id": "b0000000-0000-0000-0000-000000000001",
    "session_id": ASSISTANT_SESSION_ID,
    "session_revision": 1,
    "report": {
        "schema_version": "career-coach-report-v1",
        "status": "completed",
        "session_id": ASSISTANT_SESSION_ID,
        "session_revision": 1,
        "summary": "지원 준비의 우선순위를 정리했습니다.",
        "strengths": ["목표 직무가 구체적입니다."],
        "improvements": ["지원 근거를 보강해야 합니다."],
        "priority_actions": ["오늘 지원서 한 문단을 고칩니다."],
    },
    "created_at": "2026-08-11T10:05:00+09:00",
}


def proposal_view(**changes: Any) -> dict[str, Any]:
    proposal = {
        "id": PROPOSAL_ID,
        "request_id": "80000000-0000-0000-0000-000000000001",
        "decision_status": "pending",
        "title": "백엔드 로드맵",
        "summary": "API 역량을 강화합니다.",
        "generated_on": "2026-08-10",
        "starts_on": "2026-08-10",
        "ends_on": "2026-09-06",
        "duration_days": 28,
        "milestones": [],
        "days": [],
        "total_task_count": 2,
        "proposal_hash": "c" * 64,
        "profile_hash": "d" * 64,
        "assessment_result_id": RESULT_ID,
        "schema_version": "profile-plan-proposal-v1",
        "model_name": "gemini-test",
        "prompt_version": "proposal-v1",
        "api_version": "v1",
        "outline_prompt_version": "outline-v1",
        "tasks_prompt_version": "tasks-v1",
        "applied_plan_id": None,
        "decided_at": None,
        "created_at": "2026-08-10T09:00:00+09:00",
        "requested_start_on": "2026-08-17",
        "requested_end_on": "2026-08-23",
        "has_previous": True,
        "has_next": True,
    }
    proposal.update(changes)
    return proposal


def plan_view(**changes: Any) -> dict[str, Any]:
    plan = {
        "id": PLAN_ID,
        "proposal_result_id": PROPOSAL_ID,
        "proposal_hash": "c" * 64,
        "profile_hash": "d" * 64,
        "assessment_result_id": RESULT_ID,
        "title": "백엔드 로드맵",
        "summary": "API 역량을 강화합니다.",
        "starts_on": "2026-08-10",
        "ends_on": "2026-09-06",
        "duration_days": 28,
        "status": "active",
        "milestones": [],
        "days": [
            {
                "plan_day": 8,
                "date": "2026-08-17",
                "completed_task_count": 1,
                "total_task_count": 2,
                "achieved": False,
                "achieved_at": None,
                "earned_exp": 0,
                "tasks": [
                    {
                        "id": TASK_ID_1,
                        "plan_day": 8,
                        "slot": 1,
                        "date": "2026-08-17",
                        "title": "API 과제",
                        "description": "테스트 작성",
                        "status": "pending",
                        "completed_at": None,
                    },
                    {
                        "id": TASK_ID_2,
                        "plan_day": 8,
                        "slot": 2,
                        "date": "2026-08-17",
                        "title": "두 번째 과제",
                        "description": "반복 연습",
                        "status": "completed",
                        "completed_at": "2026-08-17T10:00:00+09:00",
                    },
                ],
            }
        ],
        "total_task_count": 2,
        "completed_task_count": 1,
        "percent": 50,
        "user_exp": 20,
        "schema_version": "profile-plan-proposal-v1",
        "model_name": "gemini-test",
        "prompt_version": "proposal-v1",
        "api_version": "v1",
        "outline_prompt_version": "outline-v1",
        "tasks_prompt_version": "tasks-v1",
        "activated_at": "2026-08-10T09:00:00+09:00",
        "ended_at": None,
        "restart_offer_status": "not_due",
        "restart_prompted_at": None,
        "requested_start_on": "2026-08-17",
        "requested_end_on": "2026-08-23",
        "has_previous": True,
        "has_next": True,
    }
    plan.update(changes)
    return plan


def completed_daily_goal_view() -> tuple[dict[str, Any], dict[str, Any]]:
    refreshed = plan_view()
    refreshed["days"][0]["tasks"][0].update(
        status="completed",
        completed_at="2026-08-17T11:00:00+09:00",
    )
    refreshed["days"][0].update(
        completed_task_count=2,
        achieved=True,
        achieved_at="2026-08-17T11:00:00+09:00",
        earned_exp=20,
    )
    refreshed.update(completed_task_count=2, percent=100, user_exp=40)
    patch = {
        **refreshed["days"][0]["tasks"][0],
        "completed_task_count": 2,
        "total_task_count": 2,
        "percent": 100,
        "day_completed_task_count": 2,
        "day_total_task_count": 2,
        "achieved": True,
        "achieved_at": "2026-08-17T11:00:00+09:00",
        "earned_exp": 20,
        "exp_delta": 20,
        "user_exp": 40,
    }
    return patch, refreshed


def today_quest_view(**changes: Any) -> dict[str, Any]:
    task = {
        "id": TASK_ID_1,
        "plan_day": 8,
        "slot": 1,
        "date": "2026-08-17",
        "scheduled_at": "2026-08-17T09:30:00+09:00",
        "title": "API 과제",
        "description": "테스트 작성",
        "status": "pending",
        "completed_at": None,
    }
    view = {
        "date": "2026-08-17",
        "plan_id": PLAN_ID,
        "plan_title": "백엔드 로드맵",
        "quests": [task],
        "completed_count": 0,
        "total_count": 1,
        "percent": 0,
        "achieved": False,
        "earned_exp": 0,
        "user_exp": 20,
    }
    view.update(changes)
    return view


def today_quest_patch(**changes: Any) -> dict[str, Any]:
    patch = {
        "id": TASK_ID_1,
        "plan_day": 8,
        "slot": 1,
        "date": "2026-08-17",
        "scheduled_at": "2026-08-17T09:30:00+09:00",
        "title": "API 과제",
        "description": "테스트 작성",
        "status": "completed",
        "completed_at": "2026-08-17T11:00:00+09:00",
        "completed_task_count": 1,
        "total_task_count": 1,
        "percent": 100,
        "day_completed_task_count": 1,
        "day_total_task_count": 1,
        "achieved": True,
        "achieved_at": "2026-08-17T11:00:00+09:00",
        "earned_exp": 20,
        "exp_delta": 20,
        "user_exp": 40,
    }
    patch.update(changes)
    return patch


NOTICES = [
    {
        "id": "91000000-0000-0000-0000-000000000001",
        "title": "서비스 점검 안내",
        "content": "일시 점검이 예정되어 있습니다.",
        "is_pinned": True,
        "published_at": "2026-08-09T09:00:00+09:00",
        "expires_at": None,
    }
]


def plans_summary_view(**changes: Any) -> dict[str, Any]:
    view = {
        "user_exp": 40,
        "plan_count": 2,
        "aggregate_total_task_count": 6,
        "aggregate_completed_task_count": 5,
        "aggregate_percent": 83,
        "plans": [
            {
                "id": PLAN_ID,
                "title": "백엔드 로드맵",
                "status": "active",
                "starts_on": "2026-08-10",
                "ends_on": "2026-08-16",
                "duration_days": 7,
                "total_task_count": 3,
                "completed_task_count": 2,
                "percent": 66,
                "activated_at": "2026-08-10T09:00:00+09:00",
                "ended_at": None,
            },
            {
                "id": "61000000-0000-0000-0000-000000000002",
                "title": "이전 로드맵",
                "status": "completed",
                "starts_on": "2026-07-01",
                "ends_on": "2026-07-03",
                "duration_days": 3,
                "total_task_count": 3,
                "completed_task_count": 3,
                "percent": 100,
                "activated_at": "2026-07-01T09:00:00+09:00",
                "ended_at": "2026-07-03T18:00:00+09:00",
            },
        ],
    }
    view.update(changes)
    return view


class ScriptedInput:
    def __init__(self, values: list[str | BaseException]) -> None:
        self.values = deque(values)
        self.secret_prompts = 0

    async def read(self, prompt: str) -> str:
        return self._next()

    async def read_secret(self, prompt: str) -> str:
        self.secret_prompts += 1
        return self._next()

    def _next(self) -> str:
        if not self.values:
            raise EOFError
        value = self.values.popleft()
        if isinstance(value, BaseException):
            raise value
        return value


class FakeApi:
    def __init__(
        self,
        *,
        signup: list[Any] | None = None,
        login: list[Any] | None = None,
        login_feed: list[Any] | None = None,
        mark_notification_read: list[Any] | None = None,
        profile: list[Any] | None = None,
        saved_jobs: list[Any] | None = None,
        saved_job_recommendation: list[Any] | None = None,
        start_assistant_session: list[Any] | None = None,
        send_assistant_message: list[Any] | None = None,
        finalize_assistant_session: list[Any] | None = None,
        start: list[Any] | None = None,
        message: list[Any] | None = None,
        onboarding_result: list[Any] | None = None,
        confirm: list[Any] | None = None,
        restart: list[Any] | None = None,
        create_plan_proposal: list[Any] | None = None,
        pending_plan_proposal: list[Any] | None = None,
        plan_proposal: list[Any] | None = None,
        accept_plan_proposal: list[Any] | None = None,
        reject_plan_proposal: list[Any] | None = None,
        active_plan: list[Any] | None = None,
        plan: list[Any] | None = None,
        set_plan_task_status: list[Any] | None = None,
        complete_plan: list[Any] | None = None,
        notices: list[Any] | None = None,
        today_quests: list[Any] | None = None,
        set_today_quest_status: list[Any] | None = None,
        plans_summary: list[Any] | None = None,
    ) -> None:
        self.results = {
            "signup": deque(signup or []),
            "login": deque(login or [None]),
            "login_feed": deque(login_feed or []),
            "mark_notification_read": deque(mark_notification_read or []),
            "profile": deque(profile or []),
            "saved_jobs": deque(saved_jobs or []),
            "saved_job_recommendation": deque(
                [None] if saved_job_recommendation is None else saved_job_recommendation
            ),
            "start_assistant_session": deque(start_assistant_session or []),
            "send_assistant_message": deque(send_assistant_message or []),
            "finalize_assistant_session": deque(finalize_assistant_session or []),
            "start": deque(start or []),
            "message": deque(message or []),
            "onboarding_result": deque(onboarding_result or []),
            "confirm": deque(confirm or []),
            "restart": deque(restart or []),
            "create_plan_proposal": deque(create_plan_proposal or []),
            "pending_plan_proposal": deque(pending_plan_proposal or []),
            "plan_proposal": deque(plan_proposal or []),
            "accept_plan_proposal": deque(accept_plan_proposal or []),
            "reject_plan_proposal": deque(reject_plan_proposal or []),
            "active_plan": deque(active_plan or []),
            "plan": deque(plan or []),
            "set_plan_task_status": deque(set_plan_task_status or []),
            "complete_plan": deque(complete_plan or []),
            "notices": deque(notices or []),
            "today_quests": deque(today_quests or []),
            "set_today_quest_status": deque(set_today_quest_status or []),
            "plans_summary": deque(plans_summary or []),
        }
        self.calls: list[tuple[Any, ...]] = []
        self.closed = False

    def _result(self, name: str) -> Any:
        item = self.results[name].popleft()
        if isinstance(item, BaseException):
            raise item
        return deepcopy(item)

    async def login(self, login_id: str, login_pw: str) -> None:
        self.calls.append(("login", login_id, login_pw))
        self._result("login")

    async def signup(self, login_id: str, login_pw: str, user_name: str) -> str:
        self.calls.append(("signup", login_id, login_pw, user_name))
        return self._result("signup")

    async def login_feed(self) -> dict[str, Any]:
        self.calls.append(("login_feed",))
        if self.results["login_feed"]:
            return self._result("login_feed")
        return {
            "window_start": "2026-08-11",
            "window_end": "2026-08-17",
            "upcoming": [],
            "changes": [],
            "unread_count": 0,
        }

    async def mark_notification_read(self, notification_id: str) -> dict[str, Any]:
        self.calls.append(("mark_notification_read", notification_id))
        if self.results["mark_notification_read"]:
            return self._result("mark_notification_read")
        return {"id": notification_id, "is_read": True}

    async def profile(self) -> dict[str, Any]:
        self.calls.append(("profile",))
        return self._result("profile")

    async def saved_jobs(self) -> list[dict[str, Any]]:
        self.calls.append(("saved_jobs",))
        return self._result("saved_jobs")

    async def saved_job_recommendation(self) -> dict[str, Any] | None:
        self.calls.append(("saved_job_recommendation",))
        return self._result("saved_job_recommendation")

    async def start_assistant_session(self) -> dict[str, Any]:
        self.calls.append(("start_assistant_session",))
        return self._result("start_assistant_session")

    async def send_assistant_message(
        self, session_id: str, expected_revision: int, text: str
    ) -> dict[str, Any]:
        self.calls.append(("send_assistant_message", session_id, expected_revision, text))
        return self._result("send_assistant_message")

    async def finalize_assistant_session(
        self, session_id: str, expected_revision: int
    ) -> dict[str, Any]:
        self.calls.append(("finalize_assistant_session", session_id, expected_revision))
        return self._result("finalize_assistant_session")

    async def start(self) -> dict[str, Any]:
        self.calls.append(("start",))
        return self._result("start")

    async def message(self, session_id: str, text: str) -> dict[str, Any]:
        self.calls.append(("message", session_id, text))
        return self._result("message")

    async def onboarding_result(self, session_id: str) -> dict[str, Any]:
        self.calls.append(("onboarding_result", session_id))
        return self._result("onboarding_result")

    async def confirm(self, session_id: str, revision: int) -> dict[str, Any]:
        self.calls.append(("confirm", session_id, revision))
        return self._result("confirm")

    async def restart(self, session_id: str) -> dict[str, Any]:
        self.calls.append(("restart", session_id))
        return self._result("restart")

    async def create_plan_proposal(
        self, request_id: str, saved_job_id: str | None = None
    ) -> dict[str, Any]:
        self.calls.append(
            ("create_plan_proposal", request_id, saved_job_id)
            if saved_job_id is not None
            else ("create_plan_proposal", request_id)
        )
        return self._result("create_plan_proposal")

    async def pending_plan_proposal(
        self, start_on: str | None = None, days: int = 7
    ) -> dict[str, Any]:
        self.calls.append(("pending_plan_proposal", start_on, days))
        return self._result("pending_plan_proposal")

    async def plan_proposal(
        self, proposal_id: str, start_on: str | None = None, days: int = 7
    ) -> dict[str, Any]:
        self.calls.append(("plan_proposal", proposal_id, start_on, days))
        return self._result("plan_proposal")

    async def accept_plan_proposal(self, proposal_id: str) -> dict[str, Any]:
        self.calls.append(("accept_plan_proposal", proposal_id))
        return self._result("accept_plan_proposal")

    async def reject_plan_proposal(self, proposal_id: str) -> dict[str, Any]:
        self.calls.append(("reject_plan_proposal", proposal_id))
        return self._result("reject_plan_proposal")

    async def active_plan(self, start_on: str | None = None, days: int = 7) -> dict[str, Any]:
        self.calls.append(("active_plan", start_on, days))
        return self._result("active_plan")

    async def plan(
        self, plan_id: str, start_on: str | None = None, days: int = 7
    ) -> dict[str, Any]:
        self.calls.append(("plan", plan_id, start_on, days))
        return self._result("plan")

    async def set_plan_task_status(self, plan_id: str, task_id: str, status: str) -> dict[str, Any]:
        self.calls.append(("set_plan_task_status", plan_id, task_id, status))
        return self._result("set_plan_task_status")

    async def complete_plan(self, plan_id: str) -> dict[str, Any]:
        self.calls.append(("complete_plan", plan_id))
        return self._result("complete_plan")

    async def notices(self) -> list[dict[str, Any]]:
        self.calls.append(("notices",))
        return self._result("notices")

    async def today_quests(self) -> dict[str, Any]:
        self.calls.append(("today_quests",))
        return self._result("today_quests")

    async def set_today_quest_status(self, task_id: str, status: str) -> dict[str, Any]:
        self.calls.append(("set_today_quest_status", task_id, status))
        return self._result("set_today_quest_status")

    async def plans_summary(self) -> dict[str, Any]:
        self.calls.append(("plans_summary",))
        return self._result("plans_summary")

    def clear_access_token(self) -> None:
        self.calls.append(("clear_access_token",))

    async def aclose(self) -> None:
        self.closed = True


def renderer() -> tuple[RichRenderer, StringIO]:
    stream = StringIO()
    console = Console(file=stream, force_terminal=False, width=120, color_system=None)
    return RichRenderer(console=console), stream


async def run_app(api: FakeApi, values: list[str | BaseException]) -> tuple[int, str]:
    output, stream = renderer()
    code = await CliApp(api=api, input_port=ScriptedInput(values), renderer=output).run()
    return code, stream.getvalue()


@pytest.mark.asyncio
async def test_full_login_conversation_review_correction_confirm_and_db_reread() -> None:
    corrected = deepcopy(REVIEW)
    corrected["assistant_message"] = "수정했습니다."
    api = FakeApi(
        profile=[ApiError(404, "PROFILE_NOT_FOUND", "raw"), PROFILE],
        start=[START],
        message=[REVIEW, corrected],
        onboarding_result=[corrected],
        confirm=[COMPLETED],
    )

    code, output = await run_app(
        api,
        ["demo.user", "secret-password", "프로필 설명", "희망 기업은 없음", "/confirm"],
    )

    assert code == 0
    assert api.closed
    assert ("message", SESSION_ID, "희망 기업은 없음") in api.calls
    assert ("onboarding_result", SESSION_ID) in api.calls
    assert ("confirm", SESSION_ID, 4) in api.calls
    assert api.calls.count(("profile",)) == 2
    assert "검증 완료" in output
    for entry in (
        "1. 프로필 보기",
        "2. 로드맵 제안 생성·검토",
        "3. 활성 로드맵",
        "4. 내 로드맵 완료율 요약",
        "5. 오늘 퀘스트",
        "6. 전체 채용 공고",
        "7. 온보딩 기반 추천 공고",
        "8. 공지 사항",
        "9. 프로필 재온보딩",
        "10. 다른 계정으로 로그인",
        "0. 종료",
    ):
        assert entry in output
    assert RESULT_ID in output
    assert "secret-password" not in output
    assert "must-not-print" not in output


@pytest.mark.asyncio
async def test_signup_continues_into_onboarding_without_logging_in_again() -> None:
    password = "  password with spaces  "
    api = FakeApi(
        signup=["new.user"],
        profile=[ApiError(404, "PROFILE_NOT_FOUND", "raw")],
        start=[START],
        message=[START],
    )

    code, output = await run_app(
        api,
        ["/signup", " New.User ", " 홍길동 ", password, password, "/quit"],
    )

    assert code == 0
    assert ("signup", "New.User", password, "홍길동") in api.calls
    assert not any(call[0] == "login" for call in api.calls)
    assert [call[0] for call in api.calls].count("profile") == 1
    assert [call[0] for call in api.calls].count("start") == 1
    assert "new.user 계정 생성 완료" in output
    assert password not in output


@pytest.mark.asyncio
async def test_signup_validation_error_keeps_signup_mode_for_corrected_input() -> None:
    api = FakeApi(
        signup=[ApiError(422, "VALIDATION_ERROR", "raw validation detail"), "new.user"],
        profile=[ApiError(404, "PROFILE_NOT_FOUND", "raw")],
        start=[START],
        message=[START],
    )

    code, output = await run_app(
        api,
        [
            "/signup",
            "bad",
            "홍길동",
            "password",
            "password",
            "new.user",
            "홍길동",
            "correct-password",
            "correct-password",
            "/quit",
        ],
    )

    assert code == 0
    assert [call[0] for call in api.calls].count("signup") == 2
    assert not any(call[0] == "login" for call in api.calls)
    assert "아이디는 영문자" in output
    assert "raw validation detail" not in output


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        ApiError(503, "SERVICE_UNAVAILABLE", "raw infrastructure detail", retryable=True),
        ApiError(503, "API_ERROR", "raw gateway detail", retryable=True),
        ApiError(503, "CLIENT_TIMEOUT", "raw timeout detail", retryable=True),
        ApiError(503, "CLIENT_NETWORK_ERROR", "raw network detail", retryable=True),
    ],
)
async def test_ambiguous_signup_failure_returns_to_login_with_recovery_guidance(
    error: ApiError,
) -> None:
    api = FakeApi(signup=[error], profile=[PROFILE])

    code, output = await run_app(
        api,
        [
            "/signup",
            "new.user",
            "홍길동",
            "password",
            "password",
            "new.user",
            "password",
        ],
    )

    assert code == 0
    assert [call[0] for call in api.calls] == [
        "signup",
        "login",
        "login_feed",
        "profile",
    ]
    assert "계정이 생성되었을 수 있으니 로그인해주세요" in output
    assert "raw" not in output


@pytest.mark.asyncio
async def test_authentication_help_advertises_signup_from_login_prompt() -> None:
    api = FakeApi(profile=[PROFILE])

    code, output = await run_app(api, ["/help", "demo.user", "password"])

    assert code == 0
    assert "/signup" in output
    assert "/login" in output


@pytest.mark.asyncio
async def test_quit_at_signup_password_confirmation_exits_without_signup() -> None:
    api = FakeApi()

    code, output = await run_app(
        api,
        ["/signup", "new.user", "홍길동", "password", "/quit", "/quit"],
    )

    assert code == 0
    assert not any(call[0] == "signup" for call in api.calls)
    assert "비밀번호 확인이 일치하지 않습니다" not in output


@pytest.mark.asyncio
async def test_login_command_from_signup_password_returns_to_login_prompt() -> None:
    api = FakeApi(profile=[PROFILE])

    code, _ = await run_app(
        api,
        [
            "/signup",
            "new.user",
            "홍길동",
            "/login",
            "demo.user",
            "password",
            "/quit",
        ],
    )

    assert code == 0
    assert [call[0] for call in api.calls] == ["login", "login_feed", "profile"]


@pytest.mark.asyncio
async def test_signup_password_mismatch_reprompts_without_sending_first_password() -> None:
    api = FakeApi(
        signup=["new.user"],
        profile=[ApiError(404, "PROFILE_NOT_FOUND", "raw")],
        start=[START],
    )

    code, output = await run_app(
        api,
        [
            "/signup",
            "new.user",
            "홍길동",
            "first-password",
            "different-password",
            "correct-password",
            "correct-password",
            "/quit",
        ],
    )

    assert code == 0
    assert ("signup", "new.user", "correct-password", "홍길동") in api.calls
    assert not any("first-password" in call for call in api.calls)
    assert "비밀번호 확인이 일치하지 않습니다" in output
    assert "first-password" not in output
    assert "correct-password" not in output


@pytest.mark.asyncio
async def test_signup_duplicate_returns_to_login_without_printing_raw_detail() -> None:
    api = FakeApi(
        signup=[ApiError(409, "LOGIN_ID_ALREADY_EXISTS", "raw duplicate detail")],
        profile=[PROFILE],
    )

    code, output = await run_app(
        api,
        [
            "/signup",
            "existing.user",
            "홍길동",
            "password",
            "password",
            "existing.user",
            "password",
        ],
    )

    assert code == 0
    assert [call[0] for call in api.calls] == [
        "signup",
        "login",
        "login_feed",
        "profile",
    ]
    assert "이미 사용 중인 아이디" in output
    assert "raw duplicate detail" not in output


@pytest.mark.asyncio
async def test_help_at_signup_confirmation_preserves_password_for_confirmation() -> None:
    api = FakeApi(
        signup=["new.user"],
        profile=[ApiError(404, "PROFILE_NOT_FOUND", "raw")],
        start=[START],
    )

    code, output = await run_app(
        api,
        ["/signup", "new.user", "홍길동", "password", "/help", "password", "/quit"],
    )

    assert code == 0
    assert ("signup", "new.user", "password", "홍길동") in api.calls
    assert "현재 단계: 회원가입" in output


@pytest.mark.asyncio
@pytest.mark.parametrize("password", ["/unknown", " /help "])
async def test_slash_prefixed_passwords_are_preserved_instead_of_treated_as_commands(
    password: str,
) -> None:
    api = FakeApi(profile=[PROFILE])

    code, output = await run_app(api, ["demo.user", password, "/quit"])

    assert code == 0
    assert ("login", "demo.user", password) in api.calls
    assert password not in output


@pytest.mark.asyncio
async def test_existing_profile_enters_the_numbered_main_menu_without_starting_onboarding() -> None:
    api = FakeApi(profile=[PROFILE])

    code, output = await run_app(api, ["demo.user", "secret-password", "0"])

    assert code == 0
    assert ("start",) not in api.calls
    assert "기존 저장 프로필" in output
    assert "백엔드 개발자" in output
    for entry in (
        "1. 프로필 보기",
        "2. 로드맵 제안 생성·검토",
        "3. 활성 로드맵",
        "4. 내 로드맵 완료율 요약",
        "5. 오늘 퀘스트",
        "6. 전체 채용 공고",
        "7. 온보딩 기반 추천 공고",
        "8. 공지 사항",
        "9. 프로필 재온보딩",
        "10. 다른 계정으로 로그인",
        "11. AI 취업 코치 상담",
        "0. 종료",
    ):
        assert entry in output


@pytest.mark.asyncio
async def test_assistant_menu_conversation_finalizes_report_and_returns_to_main_menu() -> None:
    api = FakeApi(
        profile=[PROFILE],
        start=[AssertionError("상담 메뉴에서 온보딩을 시작하면 안 됩니다.")],
        start_assistant_session=[ASSISTANT_START],
        send_assistant_message=[ASSISTANT_MESSAGE],
        finalize_assistant_session=[ASSISTANT_REPORT],
    )

    code, output = await run_app(
        api,
        ["demo.user", "secret-password", "11", "면접 준비를 도와줘", "/finish", "0"],
    )

    assert code == 0
    assert ("start_assistant_session",) in api.calls
    assert (
        "send_assistant_message",
        ASSISTANT_SESSION_ID,
        0,
        "면접 준비를 도와줘",
    ) in api.calls
    assert ("finalize_assistant_session", ASSISTANT_SESSION_ID, 1) in api.calls
    assert ("start",) not in api.calls
    assert "반가워요. 취업 고민을 알려주세요." in output
    assert "[bold]지원 근거[/bold]를 먼저 정리해보세요." in output
    assert "지원 준비의 우선순위를 정리했습니다." in output
    assert output.count("메인 메뉴") >= 2


@pytest.mark.asyncio
async def test_assistant_finish_requires_a_user_message_before_calling_finalize() -> None:
    api = FakeApi(
        profile=[PROFILE],
        start_assistant_session=[ASSISTANT_START],
        send_assistant_message=[ASSISTANT_MESSAGE],
        finalize_assistant_session=[ASSISTANT_REPORT],
    )

    code, output = await run_app(
        api,
        ["demo.user", "secret-password", "11", "/finish", "질문", "/finish", "0"],
    )

    assert code == 0
    assert [call[0] for call in api.calls].count("finalize_assistant_session") == 1
    assert "메시지를 한 번 이상 보내주세요." in output


@pytest.mark.asyncio
async def test_assistant_malformed_start_response_returns_to_menu_without_crashing() -> None:
    api = FakeApi(
        profile=[PROFILE],
        start_assistant_session=[[{"provider_raw_response": "MUST_NOT_PRINT"}]],
    )

    code, output = await run_app(
        api,
        ["demo.user", "secret-password", "11", "0"],
    )

    assert code == 0
    assert "상담 시작 응답을 확인할 수 없습니다." in output
    assert "MUST_NOT_PRINT" not in output


@pytest.mark.asyncio
async def test_assistant_rejects_mismatched_embedded_report_identity() -> None:
    mismatched = deepcopy(ASSISTANT_REPORT)
    mismatched["report"]["session_id"] = "a0000000-0000-0000-0000-000000000002"
    api = FakeApi(
        profile=[PROFILE],
        start_assistant_session=[ASSISTANT_START],
        send_assistant_message=[ASSISTANT_MESSAGE],
        finalize_assistant_session=[mismatched],
    )

    code, output = await run_app(
        api,
        ["demo.user", "secret-password", "11", "질문", "/finish", "0"],
    )

    assert code == 0
    assert "상담 보고서 응답을 확인할 수 없습니다." in output
    assert "지원 준비의 우선순위를 정리했습니다." not in output


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["message", "finalize"])
async def test_assistant_data_integrity_error_ends_invalid_session(stage: str) -> None:
    integrity_error = ApiError(
        500,
        "ASSISTANT_DATA_INTEGRITY_ERROR",
        "MUST_NOT_PRINT::integrity",
    )
    api_options: dict[str, list[Any]] = {
        "profile": [PROFILE],
        "start_assistant_session": [ASSISTANT_START],
    }
    values = ["demo.user", "secret-password", "11", "질문"]
    if stage == "message":
        api_options["send_assistant_message"] = [integrity_error]
    else:
        api_options["send_assistant_message"] = [ASSISTANT_MESSAGE]
        api_options["finalize_assistant_session"] = [integrity_error]
        values.append("/finish")
    values.append("0")

    code, output = await run_app(FakeApi(**api_options), values)

    assert code == 0
    assert "상담 데이터를 검증하지 못했습니다. 새 상담을 시작해주세요." in output
    assert "MUST_NOT_PRINT" not in output


@pytest.mark.asyncio
async def test_main_menu_has_no_alternate_slash_actions() -> None:
    api = FakeApi(profile=[PROFILE])

    code, output = await run_app(
        api, ["demo.user", "secret-password", "/profile", "/proposal", "0"]
    )

    assert code == 0
    assert api.calls == [
        ("login", "demo.user", "secret-password"),
        ("login_feed",),
        ("profile",),
    ]
    assert output.count("/help") >= 2


@pytest.mark.asyncio
async def test_notices_choice_fetches_and_renders_published_notices() -> None:
    api = FakeApi(profile=[PROFILE], notices=[NOTICES])

    code, output = await run_app(api, ["demo.user", "secret-password", "8", "0"])

    assert code == 0
    assert api.calls.count(("notices",)) == 1
    assert "서비스 점검 안내" in output
    assert "일시 점검이 예정되어 있습니다." in output
    assert "고정" in output


@pytest.mark.asyncio
async def test_notices_choice_renders_empty_state() -> None:
    api = FakeApi(profile=[PROFILE], notices=[[]])

    code, output = await run_app(api, ["demo.user", "secret-password", "8", "0"])

    assert code == 0
    assert "게시 중인 공지가 없습니다." in output


@pytest.mark.asyncio
async def test_plans_summary_choice_renders_aggregate_and_per_plan_completion() -> None:
    api = FakeApi(profile=[PROFILE], plans_summary=[plans_summary_view()])

    code, output = await run_app(api, ["demo.user", "secret-password", "4", "0"])

    assert code == 0
    assert api.calls.count(("plans_summary",)) == 1
    assert "통합 완료율 83%" in output
    assert "로드맵 2개" in output
    assert "누적 EXP 40" in output
    assert "백엔드 로드맵" in output
    assert "이전 로드맵" in output
    assert "66%" in output
    assert "100%" in output


@pytest.mark.asyncio
async def test_plans_summary_choice_renders_empty_state() -> None:
    empty = plans_summary_view(
        plan_count=0,
        aggregate_total_task_count=0,
        aggregate_completed_task_count=0,
        aggregate_percent=0,
        plans=[],
    )
    api = FakeApi(profile=[PROFILE], plans_summary=[empty])

    code, output = await run_app(api, ["demo.user", "secret-password", "4", "0"])

    assert code == 0
    assert "생성된 로드맵이 없습니다." in output


@pytest.mark.asyncio
async def test_today_quests_choice_with_no_active_plan_renders_empty_state() -> None:
    no_plan = today_quest_view(
        plan_id=None,
        plan_title=None,
        quests=[],
        completed_count=0,
        total_count=0,
        percent=0,
        achieved=False,
        earned_exp=0,
    )
    api = FakeApi(profile=[PROFILE], today_quests=[no_plan])

    code, output = await run_app(api, ["demo.user", "secret-password", "5", "0"])

    assert code == 0
    assert api.calls.count(("today_quests",)) == 1
    assert "활성 계획이 없어" in output


@pytest.mark.asyncio
async def test_today_quests_done_patches_quest_and_re_renders_with_exp_notice() -> None:
    refreshed = today_quest_view(
        completed_count=1,
        percent=100,
        achieved=True,
        earned_exp=20,
        user_exp=40,
    )
    refreshed["quests"][0].update(
        status="completed",
        completed_at="2026-08-17T11:00:00+09:00",
    )
    patch = today_quest_patch()
    api = FakeApi(
        profile=[PROFILE],
        today_quests=[today_quest_view(), refreshed],
        set_today_quest_status=[patch],
    )

    code, output = await run_app(
        api, ["demo.user", "secret-password", "5", "/done 1", "/back", "0"]
    )

    assert code == 0
    assert ("set_today_quest_status", TASK_ID_1, "completed") in api.calls
    assert api.calls.count(("today_quests",)) == 2
    assert "일일 목표 달성 · +20 EXP · 누적 40 EXP" in output


@pytest.mark.asyncio
async def test_today_quests_undo_reverses_exp_and_keeps_numbering_in_sync() -> None:
    done_view = today_quest_view(
        completed_count=1,
        percent=100,
        achieved=True,
        earned_exp=20,
        user_exp=40,
    )
    done_view["quests"][0].update(
        status="completed",
        completed_at="2026-08-17T11:00:00+09:00",
    )
    undone = today_quest_view()
    patch = today_quest_patch(
        status="pending",
        completed_at=None,
        completed_task_count=0,
        percent=0,
        day_completed_task_count=0,
        achieved=False,
        achieved_at=None,
        earned_exp=0,
        exp_delta=-20,
        user_exp=20,
    )
    api = FakeApi(
        profile=[PROFILE],
        today_quests=[done_view, undone],
        set_today_quest_status=[patch],
    )

    code, output = await run_app(
        api, ["demo.user", "secret-password", "5", "/undo 1", "/back", "0"]
    )

    assert code == 0
    assert ("set_today_quest_status", TASK_ID_1, "pending") in api.calls
    assert "일일 목표 달성 취소 · -20 EXP · 누적 20 EXP" in output


@pytest.mark.asyncio
async def test_today_quests_done_with_unknown_number_makes_no_api_call() -> None:
    api = FakeApi(profile=[PROFILE], today_quests=[today_quest_view()])

    code, output = await run_app(
        api, ["demo.user", "secret-password", "5", "/done 99", "/back", "0"]
    )

    assert code == 0
    assert not any(call[0] == "set_today_quest_status" for call in api.calls)
    assert "현재 화면의 과제 번호를 입력해주세요." in output


@pytest.mark.asyncio
async def test_saved_jobs_choice_fetches_and_renders_the_shared_job_list() -> None:
    api = FakeApi(profile=[PROFILE], saved_jobs=[SAVED_JOBS])

    code, output = await run_app(api, ["demo.user", "secret-password", "6", "0"])

    assert code == 0
    assert api.calls.count(("saved_jobs",)) == 1
    assert "전체 채용 공고 (1건)" in output
    assert "예시회사" in output
    assert "백엔드 개발자" in output
    assert "https://example.com/jobs/backend" in output


@pytest.mark.asyncio
async def test_recommendation_choice_uses_existing_onboarding_profile() -> None:
    api = FakeApi(
        profile=[PROFILE],
        saved_job_recommendation=[SAVED_JOB_RECOMMENDATION],
    )

    code, output = await run_app(api, ["demo.user", "secret-password", "7", "0"])

    assert code == 0
    assert api.calls.count(("saved_job_recommendation",)) == 1
    assert ("start",) not in api.calls
    assert "희망 환경 맞춤 추천" in output
    assert "일치도 100점" in output
    assert "예시회사" in output


@pytest.mark.asyncio
async def test_selected_recommendation_is_used_for_plan_proposal_generation() -> None:
    api = FakeApi(
        profile=[PROFILE],
        saved_job_recommendation=[SAVED_JOB_RECOMMENDATION],
        pending_plan_proposal=[ApiError(404, "PLAN_PROPOSAL_NOT_FOUND", "raw pending detail")],
        create_plan_proposal=[proposal_view()],
    )

    code, output = await run_app(
        api,
        [
            "demo.user",
            "secret-password",
            "7",
            "y",
            "2",
            "y",
            "/back",
            "0",
        ],
    )

    assert code == 0
    create_call = next(call for call in api.calls if call[0] == "create_plan_proposal")
    assert create_call[2] == SAVED_JOBS[0]["id"]
    assert "추천 공고를 선택했습니다" in output


@pytest.mark.asyncio
async def test_completed_onboarding_immediately_renders_environment_recommendation() -> None:
    api = FakeApi(
        profile=[ApiError(404, "PROFILE_NOT_FOUND", "raw"), PROFILE],
        start=[REVIEW],
        onboarding_result=[REVIEW],
        confirm=[COMPLETED],
        saved_job_recommendation=[SAVED_JOB_RECOMMENDATION],
    )

    code, output = await run_app(
        api,
        ["demo.user", "secret-password", "/confirm", "0"],
    )

    assert code == 0
    assert api.calls.count(("saved_job_recommendation",)) == 1
    assert api.calls.index(("profile",)) < api.calls.index(("saved_job_recommendation",))
    assert "희망 환경 맞춤 추천" in output
    assert "일치도 100점" in output
    assert "예시회사" in output


@pytest.mark.asyncio
async def test_proposal_choice_reads_pending_first_and_decline_never_generates() -> None:
    api = FakeApi(
        profile=[PROFILE],
        pending_plan_proposal=[ApiError(404, "PLAN_PROPOSAL_NOT_FOUND", "raw pending detail")],
    )

    code, output = await run_app(api, ["demo.user", "secret-password", "2", "n", "0"])

    assert code == 0
    assert ("pending_plan_proposal", None, 7) in api.calls
    assert not any(call[0] == "create_plan_proposal" for call in api.calls)
    assert "raw pending detail" not in output


@pytest.mark.asyncio
async def test_generation_retry_reuses_one_uuid_only_after_explicit_menu_choice() -> None:
    generated = proposal_view()
    api = FakeApi(
        profile=[PROFILE],
        pending_plan_proposal=[
            ApiError(404, "PLAN_PROPOSAL_NOT_FOUND", "raw"),
            ApiError(404, "PLAN_PROPOSAL_NOT_FOUND", "raw"),
        ],
        create_plan_proposal=[
            ApiError(503, "CLIENT_TIMEOUT", "raw", retryable=True),
            generated,
        ],
    )

    code, output = await run_app(
        api,
        ["demo.user", "secret-password", "2", "y", "2", "yes", "/back", "0"],
    )

    assert code == 0
    create_calls = [call for call in api.calls if call[0] == "create_plan_proposal"]
    assert len(create_calls) == 2
    assert create_calls[0][1] == create_calls[1][1]
    assert str(UUID(create_calls[0][1])) == create_calls[0][1]
    assert output.count("서버 응답 시간이 초과") == 1


@pytest.mark.asyncio
async def test_generation_401_keeps_uuid_but_waits_for_relogin_and_explicit_choice() -> None:
    api = FakeApi(
        login=[None, None],
        profile=[PROFILE, PROFILE],
        pending_plan_proposal=[
            ApiError(404, "PLAN_PROPOSAL_NOT_FOUND", "raw"),
            ApiError(404, "PLAN_PROPOSAL_NOT_FOUND", "raw"),
        ],
        create_plan_proposal=[
            ApiError(401, "UNAUTHORIZED", "raw"),
            proposal_view(),
        ],
    )

    code, output = await run_app(
        api,
        [
            "first.user",
            "pw-one",
            "2",
            "y",
            "second.user",
            "pw-two",
            "2",
            "y",
            "/back",
            "0",
        ],
    )

    assert code == 0
    create_calls = [call for call in api.calls if call[0] == "create_plan_proposal"]
    assert len(create_calls) == 2
    assert create_calls[0][1] == create_calls[1][1]
    assert [call[0] for call in api.calls].count("clear_access_token") == 1
    assert "raw" not in output


@pytest.mark.asyncio
async def test_recovered_pending_proposal_clears_retained_generation_uuid() -> None:
    recovered = proposal_view()
    api = FakeApi(
        profile=[PROFILE],
        pending_plan_proposal=[
            ApiError(404, "PLAN_PROPOSAL_NOT_FOUND", "raw"),
            recovered,
            ApiError(404, "PLAN_PROPOSAL_NOT_FOUND", "raw"),
        ],
        create_plan_proposal=[
            ApiError(503, "CLIENT_TIMEOUT", "raw", retryable=True),
            proposal_view(),
        ],
        reject_plan_proposal=[{}],
    )

    code, _ = await run_app(
        api,
        [
            "demo.user",
            "secret-password",
            "2",
            "y",
            "2",
            "/reject",
            "2",
            "y",
            "/back",
            "0",
        ],
    )

    assert code == 0
    create_calls = [call for call in api.calls if call[0] == "create_plan_proposal"]
    assert len(create_calls) == 2
    assert create_calls[0][1] != create_calls[1][1]


@pytest.mark.asyncio
async def test_switch_account_discards_user_scoped_retained_generation_uuid() -> None:
    api = FakeApi(
        login=[None, None],
        profile=[PROFILE, PROFILE],
        pending_plan_proposal=[
            ApiError(404, "PLAN_PROPOSAL_NOT_FOUND", "raw"),
            ApiError(404, "PLAN_PROPOSAL_NOT_FOUND", "raw"),
        ],
        create_plan_proposal=[
            ApiError(503, "CLIENT_TIMEOUT", "raw", retryable=True),
            proposal_view(),
        ],
    )

    code, _ = await run_app(
        api,
        [
            "first.user",
            "pw-one",
            "2",
            "y",
            "10",
            "second.user",
            "pw-two",
            "2",
            "y",
            "/back",
            "0",
        ],
    )

    assert code == 0
    create_calls = [call for call in api.calls if call[0] == "create_plan_proposal"]
    assert len(create_calls) == 2
    assert create_calls[0][1] != create_calls[1][1]


@pytest.mark.asyncio
async def test_proposal_navigation_uses_prior_inclusive_window_and_strict_date() -> None:
    initial = proposal_view()
    next_page = proposal_view(requested_start_on="2026-08-24", requested_end_on="2026-08-30")
    previous_page = proposal_view()
    dated_page = proposal_view(requested_start_on="2026-08-12", requested_end_on="2026-08-18")
    api = FakeApi(
        profile=[PROFILE],
        pending_plan_proposal=[initial],
        plan_proposal=[next_page, previous_page, dated_page],
    )

    code, _ = await run_app(
        api,
        [
            "demo.user",
            "secret-password",
            "2",
            "/next",
            "/prev",
            "/date 2026-02-30",
            "/date 2026-08-12",
            "/back",
            "0",
        ],
    )

    assert code == 0
    assert [call for call in api.calls if call[0] == "plan_proposal"] == [
        ("plan_proposal", PROPOSAL_ID, "2026-08-24", 7),
        ("plan_proposal", PROPOSAL_ID, "2026-08-17", 7),
        ("plan_proposal", PROPOSAL_ID, "2026-08-12", 7),
    ]


@pytest.mark.asyncio
async def test_clipped_final_proposal_page_keeps_the_seven_day_window_for_prev() -> None:
    clipped = proposal_view(
        requested_start_on="2026-09-04",
        requested_end_on="2026-09-06",
        has_previous=True,
        has_next=False,
    )
    api = FakeApi(
        profile=[PROFILE],
        pending_plan_proposal=[clipped],
        plan_proposal=[proposal_view()],
    )

    code, _ = await run_app(api, ["demo.user", "secret-password", "2", "/prev", "/back", "0"])

    assert code == 0
    assert ("plan_proposal", PROPOSAL_ID, "2026-08-28", 7) in api.calls


@pytest.mark.asyncio
async def test_proposal_prev_clamps_near_start_window_to_overall_start() -> None:
    near_start = proposal_view(
        requested_start_on="2026-08-12",
        requested_end_on="2026-08-18",
        has_previous=True,
    )
    api = FakeApi(
        profile=[PROFILE],
        pending_plan_proposal=[near_start],
        plan_proposal=[proposal_view()],
    )

    code, _ = await run_app(api, ["demo.user", "secret-password", "2", "/prev", "/back", "0"])

    assert code == 0
    assert ("plan_proposal", PROPOSAL_ID, "2026-08-10", 7) in api.calls


@pytest.mark.asyncio
async def test_disabled_proposal_navigation_makes_no_request() -> None:
    api = FakeApi(
        profile=[PROFILE],
        pending_plan_proposal=[proposal_view(has_previous=False, has_next=False)],
    )

    code, _ = await run_app(
        api,
        ["demo.user", "secret-password", "2", "/next", "/prev", "/back", "0"],
    )

    assert code == 0
    assert not any(call[0] == "plan_proposal" for call in api.calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["20260812", "2026-W33-1"])
async def test_proposal_date_requires_exact_calendar_date_syntax(value: str) -> None:
    api = FakeApi(profile=[PROFILE], pending_plan_proposal=[proposal_view()])

    code, _ = await run_app(
        api,
        ["demo.user", "secret-password", "2", f"/date {value}", "/back", "0"],
    )

    assert code == 0
    assert not any(call[0] == "plan_proposal" for call in api.calls)


@pytest.mark.asyncio
async def test_accept_rereads_active_plan_and_enters_plan_only_on_exact_match() -> None:
    proposal = proposal_view()
    active = plan_view()
    api = FakeApi(
        profile=[PROFILE],
        pending_plan_proposal=[proposal],
        accept_plan_proposal=[{}],
        active_plan=[active],
    )

    code, output = await run_app(
        api, ["demo.user", "secret-password", "2", "/accept", "/back", "0"]
    )

    assert code == 0
    assert ("accept_plan_proposal", PROPOSAL_ID) in api.calls
    assert ("active_plan", None, 7) in api.calls
    assert "수락" in output


@pytest.mark.asyncio
async def test_accept_mismatch_stays_in_proposal_without_claiming_success() -> None:
    api = FakeApi(
        profile=[PROFILE],
        pending_plan_proposal=[proposal_view()],
        accept_plan_proposal=[{}],
        active_plan=[plan_view(proposal_hash="different")],
    )

    code, output = await run_app(
        api, ["demo.user", "secret-password", "2", "/accept", "/back", "0"]
    )

    assert code == 0
    assert "활성 계획을 검증하지 못했습니다" in output
    assert "수락 완료" not in output


@pytest.mark.asyncio
async def test_reject_not_pending_reports_error_and_returns_to_main_menu() -> None:
    api = FakeApi(
        profile=[PROFILE],
        pending_plan_proposal=[proposal_view()],
        reject_plan_proposal=[ApiError(409, "PLAN_PROPOSAL_NOT_PENDING", "raw decision detail")],
    )

    code, output = await run_app(api, ["demo.user", "secret-password", "2", "/reject", "0"])

    assert code == 0
    assert output.count("1. 프로필 보기") == 2
    assert "이미 처리된 로드맵 제안" in output
    assert "raw decision detail" not in output


@pytest.mark.asyncio
async def test_plan_task_numbers_are_rebuilt_after_each_patch_and_refetch() -> None:
    first = plan_view()
    reversed_tasks = deepcopy(first["days"][0]["tasks"])
    reversed_tasks.reverse()
    second = plan_view(days=[{**first["days"][0], "tasks": reversed_tasks}])
    third = plan_view()
    api = FakeApi(
        profile=[PROFILE],
        active_plan=[first],
        set_plan_task_status=[{}, {}],
        plan=[second, third],
    )

    code, _ = await run_app(
        api,
        ["demo.user", "secret-password", "3", "/done 1", "/undo 1", "/back", "0"],
    )

    assert code == 0
    assert [call for call in api.calls if call[0] == "set_plan_task_status"] == [
        ("set_plan_task_status", PLAN_ID, TASK_ID_1, "completed"),
        ("set_plan_task_status", PLAN_ID, TASK_ID_2, "pending"),
    ]
    assert [call for call in api.calls if call[0] == "plan"] == [
        ("plan", PLAN_ID, "2026-08-17", 7),
        ("plan", PLAN_ID, "2026-08-17", 7),
    ]


@pytest.mark.asyncio
async def test_patch_announces_exp_only_after_canonical_refetch_matches() -> None:
    patch, refreshed = completed_daily_goal_view()
    api = FakeApi(
        profile=[PROFILE],
        active_plan=[plan_view()],
        set_plan_task_status=[patch],
        plan=[refreshed],
    )

    code, output = await run_app(
        api,
        ["demo.user", "secret-password", "3", "/done 1", "/back", "0"],
    )

    assert code == 0
    assert "일일 목표 달성" in output
    assert "+20 EXP" in output
    assert "누적 40 EXP" in output


@pytest.mark.asyncio
async def test_patch_does_not_announce_exp_when_canonical_refetch_disagrees() -> None:
    patch, _ = completed_daily_goal_view()
    api = FakeApi(
        profile=[PROFILE],
        active_plan=[plan_view()],
        set_plan_task_status=[patch],
        plan=[plan_view()],
    )

    code, output = await run_app(
        api,
        ["demo.user", "secret-password", "3", "/done 1", "/back", "0"],
    )

    assert code == 0
    assert "일일 목표 달성" not in output
    assert "+20 EXP" not in output
    assert "변경 결과를 검증하지 못했습니다" in output


@pytest.mark.asyncio
async def test_clipped_plan_page_keeps_seven_days_for_patch_refetch() -> None:
    clipped = plan_view(
        requested_start_on="2026-09-04",
        requested_end_on="2026-09-06",
        has_next=False,
    )
    api = FakeApi(
        profile=[PROFILE],
        active_plan=[clipped],
        set_plan_task_status=[{}],
        plan=[clipped],
    )

    code, _ = await run_app(api, ["demo.user", "secret-password", "3", "/done 1", "/back", "0"])

    assert code == 0
    assert ("plan", PLAN_ID, "2026-09-04", 7) in api.calls


@pytest.mark.asyncio
async def test_plan_prev_clamps_near_start_window_to_overall_start() -> None:
    near_start = plan_view(
        requested_start_on="2026-08-12",
        requested_end_on="2026-08-18",
        has_previous=True,
    )
    api = FakeApi(
        profile=[PROFILE],
        active_plan=[near_start],
        plan=[plan_view()],
    )

    code, _ = await run_app(api, ["demo.user", "secret-password", "3", "/prev", "/back", "0"])

    assert code == 0
    assert ("plan", PLAN_ID, "2026-08-10", 7) in api.calls


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["20260812", "2026-W33-1"])
async def test_plan_date_requires_exact_calendar_date_syntax(value: str) -> None:
    api = FakeApi(profile=[PROFILE], active_plan=[plan_view()])

    code, _ = await run_app(
        api,
        ["demo.user", "secret-password", "3", f"/date {value}", "/back", "0"],
    )

    assert code == 0
    assert not any(call[0] == "plan" for call in api.calls)


@pytest.mark.asyncio
async def test_disabled_plan_navigation_and_nonvisible_task_numbers_make_no_request() -> None:
    api = FakeApi(
        profile=[PROFILE],
        active_plan=[plan_view(has_previous=False, has_next=False)],
    )

    code, _ = await run_app(
        api,
        [
            "demo.user",
            "secret-password",
            "3",
            "/next",
            "/prev",
            "/done 0",
            "/done 99",
            "/undo nope",
            "/back",
            "0",
        ],
    )

    assert code == 0
    assert not any(call[0] == "plan" for call in api.calls)
    assert not any(call[0] == "set_plan_task_status" for call in api.calls)


def test_visible_task_selection_is_number_to_immutable_uuid() -> None:
    selections = _visible_task_selections(plan_view())

    assert selections == {
        1: UUID(TASK_ID_1),
        2: UUID(TASK_ID_2),
    }
    assert all(type(number) is int and number > 0 for number in selections)
    assert all(isinstance(task_id, UUID) for task_id in selections.values())


@pytest.mark.asyncio
async def test_patch_refetch_failure_disables_mutations_until_fresh_read() -> None:
    first = plan_view(title="재조회 전 화면")
    reversed_tasks = deepcopy(first["days"][0]["tasks"])
    reversed_tasks.reverse()
    refreshed = plan_view(
        title="새로 조회한 화면",
        days=[{**first["days"][0], "tasks": reversed_tasks}],
    )
    api = FakeApi(
        profile=[PROFILE],
        active_plan=[first, refreshed],
        set_plan_task_status=[{}, {}],
        plan=[ApiError(503, "CLIENT_NETWORK_ERROR", "raw read failure"), refreshed],
    )

    code, output = await run_app(
        api,
        [
            "demo.user",
            "secret-password",
            "3",
            "/done 1",
            "/done 2",
            "/undo 1",
            "/finish",
            "/today",
            "/done 1",
            "/back",
            "0",
        ],
    )

    assert code == 0
    assert [call for call in api.calls if call[0] == "set_plan_task_status"] == [
        ("set_plan_task_status", PLAN_ID, TASK_ID_1, "completed"),
        ("set_plan_task_status", PLAN_ID, TASK_ID_2, "completed"),
    ]
    assert not any(call[0] == "complete_plan" for call in api.calls)
    assert ("active_plan", None, 7) in api.calls
    assert "새로 조회" in output
    assert output.count("재조회 전 화면") == 1
    assert "새로 조회한 화면" in output
    assert "raw read failure" not in output


@pytest.mark.parametrize(
    ("proposal_change", "active_change"),
    [
        ({"id": None}, {}),
        ({"id": "not-a-uuid"}, {"proposal_result_id": "not-a-uuid"}),
        ({"proposal_hash": None}, {}),
        ({"proposal_hash": "not-a-hash"}, {"proposal_hash": "not-a-hash"}),
        ({"title": ""}, {"title": ""}),
        ({"starts_on": "20260810"}, {"starts_on": "20260810"}),
        ({"ends_on": "2026-W36-7"}, {"ends_on": "2026-W36-7"}),
        ({"total_task_count": 0}, {"total_task_count": 0}),
        ({"total_task_count": True}, {"total_task_count": True}),
        ({}, {"proposal_result_id": None}),
    ],
)
def test_active_proposal_comparison_fails_closed_on_missing_or_malformed_fields(
    proposal_change: dict[str, Any], active_change: dict[str, Any]
) -> None:
    proposal = proposal_view(**proposal_change)
    active = plan_view(**active_change)

    assert not _active_matches_proposal(active, proposal)


def test_active_proposal_comparison_rejects_empty_payloads() -> None:
    assert not _active_matches_proposal({}, {})


@pytest.mark.asyncio
async def test_plan_navigation_and_today_use_the_documented_endpoints() -> None:
    initial = plan_view()
    next_page = plan_view(requested_start_on="2026-08-24", requested_end_on="2026-08-30")
    previous_page = plan_view()
    dated_page = plan_view(requested_start_on="2026-08-12", requested_end_on="2026-08-18")
    today_page = plan_view(requested_start_on="2026-08-10", requested_end_on="2026-08-16")
    api = FakeApi(
        profile=[PROFILE],
        active_plan=[initial, today_page],
        plan=[next_page, previous_page, dated_page],
    )

    code, _ = await run_app(
        api,
        [
            "demo.user",
            "secret-password",
            "3",
            "/next",
            "/prev",
            "/date bad",
            "/date 2026-08-12",
            "/today",
            "/back",
            "0",
        ],
    )

    assert code == 0
    assert [call for call in api.calls if call[0] == "plan"] == [
        ("plan", PLAN_ID, "2026-08-24", 7),
        ("plan", PLAN_ID, "2026-08-17", 7),
        ("plan", PLAN_ID, "2026-08-12", 7),
    ]
    assert [call for call in api.calls if call[0] == "active_plan"] == [
        ("active_plan", None, 7),
        ("active_plan", None, 7),
    ]


@pytest.mark.asyncio
async def test_finish_incomplete_stays_in_plan_then_success_returns_to_menu() -> None:
    completed = plan_view(status="completed", completed_task_count=2, percent=100)
    api = FakeApi(
        profile=[PROFILE],
        active_plan=[plan_view()],
        complete_plan=[
            ApiError(409, "PLAN_NOT_COMPLETE", "raw incomplete detail"),
            completed,
        ],
    )

    code, output = await run_app(
        api, ["demo.user", "secret-password", "3", "/finish", "/finish", "0"]
    )

    assert code == 0
    assert [call[0] for call in api.calls].count("complete_plan") == 2
    assert "완료하지 않은 과제가 있습니다" in output
    assert "raw incomplete detail" not in output


@pytest.mark.asyncio
async def test_reonboarding_pending_decline_does_not_reject_or_start() -> None:
    api = FakeApi(profile=[PROFILE], pending_plan_proposal=[proposal_view()])

    code, output = await run_app(api, ["demo.user", "secret-password", "9", "no", "0"])

    assert code == 0
    assert not any(call[0] == "reject_plan_proposal" for call in api.calls)
    assert ("start",) not in api.calls
    assert "백엔드 로드맵" in output


@pytest.mark.asyncio
async def test_reonboarding_rejects_pending_only_after_confirmation_then_starts() -> None:
    api = FakeApi(
        profile=[PROFILE],
        pending_plan_proposal=[proposal_view()],
        reject_plan_proposal=[{}],
        start=[START],
    )

    code, _ = await run_app(api, ["demo.user", "secret-password", "9", "y", "/quit"])

    assert code == 0
    assert ("reject_plan_proposal", PROPOSAL_ID) in api.calls
    assert ("start",) in api.calls


@pytest.mark.asyncio
async def test_switch_account_clears_only_local_token_and_prompts_for_credentials() -> None:
    api = FakeApi(profile=[PROFILE, PROFILE], login=[None, None])

    code, _ = await run_app(
        api,
        ["first.user", "pw-one", "10", "second.user", "pw-two", "0"],
    )

    assert code == 0
    assert [call for call in api.calls if call[0] == "login"] == [
        ("login", "first.user", "pw-one"),
        ("login", "second.user", "pw-two"),
    ]
    assert [call[0] for call in api.calls].count("clear_access_token") == 1


@pytest.mark.asyncio
async def test_mutation_401_relogs_in_without_replaying_the_mutation() -> None:
    api = FakeApi(
        login=[None, None],
        profile=[PROFILE, PROFILE],
        active_plan=[plan_view()],
        set_plan_task_status=[ApiError(401, "UNAUTHORIZED", "raw")],
    )

    code, output = await run_app(
        api,
        ["first.user", "pw-one", "3", "/done 1", "second.user", "pw-two", "0"],
    )

    assert code == 0
    assert [call[0] for call in api.calls].count("set_plan_task_status") == 1
    assert [call[0] for call in api.calls].count("clear_access_token") == 1
    assert "raw" not in output


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        "proposal_pending",
        "proposal_page",
        "proposal_accept",
        "proposal_accept_verify",
        "proposal_reject",
        "active_entry",
        "plan_page",
        "plan_complete",
        "saved_jobs_entry",
        "saved_job_recommendation_entry",
        "plans_summary_entry",
        "assistant_start",
        "assistant_message",
        "assistant_finalize",
        "reonboarding_pending",
        "reonboarding_reject",
        "reonboarding_start",
    ],
)
async def test_each_new_operation_401_relogs_in_without_automatic_replay(
    case: str,
) -> None:
    unauthorized = ApiError(401, "UNAUTHORIZED", "raw unauthorized detail")
    api_options: dict[str, list[Any]] = {
        "login": [None, None],
        "profile": [PROFILE, PROFILE],
    }
    action: list[str]
    failed_call: str

    if case == "proposal_pending":
        api_options["pending_plan_proposal"] = [unauthorized]
        action = ["2"]
        failed_call = "pending_plan_proposal"
    elif case == "proposal_page":
        api_options["pending_plan_proposal"] = [proposal_view()]
        api_options["plan_proposal"] = [unauthorized]
        action = ["2", "/date 2026-08-12"]
        failed_call = "plan_proposal"
    elif case == "proposal_accept":
        api_options["pending_plan_proposal"] = [proposal_view()]
        api_options["accept_plan_proposal"] = [unauthorized]
        action = ["2", "/accept"]
        failed_call = "accept_plan_proposal"
    elif case == "proposal_accept_verify":
        api_options["pending_plan_proposal"] = [proposal_view()]
        api_options["accept_plan_proposal"] = [{}]
        api_options["active_plan"] = [unauthorized]
        action = ["2", "/accept"]
        failed_call = "active_plan"
    elif case == "proposal_reject":
        api_options["pending_plan_proposal"] = [proposal_view()]
        api_options["reject_plan_proposal"] = [unauthorized]
        action = ["2", "/reject"]
        failed_call = "reject_plan_proposal"
    elif case == "active_entry":
        api_options["active_plan"] = [unauthorized]
        action = ["3"]
        failed_call = "active_plan"
    elif case == "plan_page":
        api_options["active_plan"] = [plan_view()]
        api_options["plan"] = [unauthorized]
        action = ["3", "/date 2026-08-12"]
        failed_call = "plan"
    elif case == "plan_complete":
        api_options["active_plan"] = [plan_view()]
        api_options["complete_plan"] = [unauthorized]
        action = ["3", "/finish"]
        failed_call = "complete_plan"
    elif case == "saved_jobs_entry":
        api_options["saved_jobs"] = [unauthorized]
        action = ["6"]
        failed_call = "saved_jobs"
    elif case == "saved_job_recommendation_entry":
        api_options["saved_job_recommendation"] = [unauthorized]
        action = ["7"]
        failed_call = "saved_job_recommendation"
    elif case == "plans_summary_entry":
        api_options["plans_summary"] = [unauthorized]
        action = ["4"]
        failed_call = "plans_summary"
    elif case == "assistant_start":
        api_options["start_assistant_session"] = [unauthorized]
        action = ["11"]
        failed_call = "start_assistant_session"
    elif case == "assistant_message":
        api_options["start_assistant_session"] = [ASSISTANT_START]
        api_options["send_assistant_message"] = [unauthorized]
        action = ["11", "지원 전략을 알려줘"]
        failed_call = "send_assistant_message"
    elif case == "assistant_finalize":
        api_options["start_assistant_session"] = [ASSISTANT_START]
        api_options["send_assistant_message"] = [ASSISTANT_MESSAGE]
        api_options["finalize_assistant_session"] = [unauthorized]
        action = ["11", "지원 전략을 알려줘", "/finish"]
        failed_call = "finalize_assistant_session"
    elif case == "reonboarding_pending":
        api_options["pending_plan_proposal"] = [unauthorized]
        action = ["9"]
        failed_call = "pending_plan_proposal"
    elif case == "reonboarding_reject":
        api_options["pending_plan_proposal"] = [proposal_view()]
        api_options["reject_plan_proposal"] = [unauthorized]
        action = ["9", "y"]
        failed_call = "reject_plan_proposal"
    else:
        api_options["pending_plan_proposal"] = [ApiError(404, "PLAN_PROPOSAL_NOT_FOUND", "raw")]
        api_options["start"] = [unauthorized]
        action = ["9"]
        failed_call = "start"

    api = FakeApi(**api_options)
    code, output = await run_app(
        api,
        ["first.user", "pw-one", *action, "second.user", "pw-two", "0"],
    )

    assert code == 0
    assert [call[0] for call in api.calls].count(failed_call) == 1
    assert [call[0] for call in api.calls].count("login") == 2
    assert [call[0] for call in api.calls].count("clear_access_token") == 1
    if case == "proposal_accept_verify":
        assert [call[0] for call in api.calls].count("accept_plan_proposal") == 1
    assert "raw unauthorized detail" not in output


@pytest.mark.asyncio
async def test_commands_are_stage_aware_and_invalid_commands_make_no_api_call() -> None:
    api = FakeApi(
        profile=[ApiError(404, "PROFILE_NOT_FOUND", "raw")],
        start=[START],
    )

    code, output = await run_app(
        api,
        ["/help", "demo.user", "secret", "/confirm", "/restart", "/unknown", "/help", "/quit"],
    )

    assert code == 0
    assert [call[0] for call in api.calls] == ["login", "login_feed", "profile", "start"]
    assert output.count("사용 가능한 명령") >= 5


@pytest.mark.asyncio
async def test_password_help_and_review_help_or_unknown_commands_make_no_extra_api_call() -> None:
    api = FakeApi(
        profile=[ApiError(404, "PROFILE_NOT_FOUND", "raw")],
        start=[REVIEW],
    )

    code, output = await run_app(
        api,
        ["demo.user", "/help", "secret", "/help", "/unknown", "/quit"],
    )

    assert code == 0
    assert [call[0] for call in api.calls] == ["login", "login_feed", "profile", "start"]
    assert output.count("사용 가능한 명령") == 3


@pytest.mark.asyncio
async def test_restart_replaces_and_renders_current_response() -> None:
    restarted = response("conversation", EMPTY_PAYLOAD, "처음부터 다시 시작합니다.")
    api = FakeApi(
        profile=[ApiError(404, "PROFILE_NOT_FOUND", "raw")],
        start=[REVIEW],
        restart=[restarted],
    )

    code, output = await run_app(api, ["id", "pw", "/restart", "/quit"])

    assert code == 0
    assert ("restart", SESSION_ID) in api.calls
    assert "처음부터 다시 시작합니다." in output


@pytest.mark.asyncio
async def test_restart_provider_error_preserves_review_and_permits_retry() -> None:
    restarted = response("conversation", EMPTY_PAYLOAD, "재시작에 성공했습니다.")
    api = FakeApi(
        profile=[ApiError(404, "PROFILE_NOT_FOUND", "raw")],
        start=[REVIEW],
        restart=[ApiError(502, "GEMINI_UNAVAILABLE", "provider raw"), restarted],
    )

    code, output = await run_app(api, ["id", "pw", "/restart", "/restart", "/quit"])

    assert code == 0
    assert [call[0] for call in api.calls].count("restart") == 2
    assert "일시적으로 불안정" in output
    assert "재시작에 성공했습니다." in output
    assert "provider raw" not in output


@pytest.mark.asyncio
async def test_confirm_revision_conflict_preserves_review_and_permits_retry() -> None:
    api = FakeApi(
        profile=[ApiError(404, "PROFILE_NOT_FOUND", "raw"), PROFILE],
        start=[REVIEW],
        onboarding_result=[REVIEW, REVIEW],
        confirm=[ApiError(409, "ONBOARDING_REVISION_CONFLICT", "raw"), COMPLETED],
    )

    code, output = await run_app(api, ["id", "pw", "/confirm", "/confirm"])

    assert code == 0
    assert [call[0] for call in api.calls].count("confirm") == 2
    assert "최신 review" in output
    assert "검증 완료" in output


@pytest.mark.asyncio
@pytest.mark.parametrize(("ending", "expected"), [(EOFError(), 0), (KeyboardInterrupt(), 130)])
async def test_eof_and_ctrl_c_have_shell_exit_codes_and_always_close(
    ending: BaseException, expected: int
) -> None:
    api = FakeApi()

    code, _ = await run_app(api, [ending])

    assert code == expected
    assert api.closed


@pytest.mark.skipif(pty is None, reason="PTY integration requires POSIX")
def test_one_terminal_ctrl_c_exits_real_cli_130_without_traceback() -> None:
    assert pty is not None
    pid, terminal_fd = pty.fork()
    if pid == 0:
        os.execv(sys.executable, [sys.executable, "-m", "app.cli.app"])

    output = bytearray()
    status: int | None = None
    deadline = time.monotonic() + 3
    try:
        while time.monotonic() < deadline and b"\xec\x95\x84\xec\x9d\xb4\xeb\x94\x94" not in output:
            readable, _, _ = select.select([terminal_fd], [], [], 0.05)
            if readable:
                output.extend(os.read(terminal_fd, 4096))
        assert b"\xec\x95\x84\xec\x9d\xb4\xeb\x94\x94" in output

        os.write(terminal_fd, b"\x03")
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            waited_pid, candidate = os.waitpid(pid, os.WNOHANG)
            if waited_pid == pid:
                status = candidate
                break
            readable, _, _ = select.select([terminal_fd], [], [], 0.05)
            if readable:
                try:
                    output.extend(os.read(terminal_fd, 4096))
                except OSError:
                    pass

        assert status is not None, "single terminal Ctrl+C did not terminate the CLI promptly"
        while True:
            readable, _, _ = select.select([terminal_fd], [], [], 0)
            if not readable:
                break
            try:
                chunk = os.read(terminal_fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            output.extend(chunk)
        assert os.waitstatus_to_exitcode(status) == 130
        assert b"Traceback" not in output
    finally:
        if status is None:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
        os.close(terminal_fd)


@pytest.mark.skipif(pty is None or termios is None, reason="getpass PTY requires POSIX")
def test_one_ctrl_c_during_real_getpass_restores_echo_and_exits_130() -> None:
    assert pty is not None
    assert termios is not None
    pid, terminal_fd = pty.fork()
    if pid == 0:
        os.execv(sys.executable, [sys.executable, "-m", "app.cli.app"])

    output = bytearray()
    status: int | None = None
    original_attributes = termios.tcgetattr(terminal_fd)
    deadline = time.monotonic() + 3
    try:
        while time.monotonic() < deadline and b"\xec\x95\x84\xec\x9d\xb4\xeb\x94\x94" not in output:
            readable, _, _ = select.select([terminal_fd], [], [], 0.05)
            if readable:
                output.extend(os.read(terminal_fd, 4096))
        assert b"\xec\x95\x84\xec\x9d\xb4\xeb\x94\x94" in output
        os.write(terminal_fd, b"demo.user\n")

        deadline = time.monotonic() + 3
        while (
            time.monotonic() < deadline
            and b"\xeb\xb9\x84\xeb\xb0\x80\xeb\xb2\x88\xed\x98\xb8" not in output
        ):
            readable, _, _ = select.select([terminal_fd], [], [], 0.05)
            if readable:
                output.extend(os.read(terminal_fd, 4096))
        assert b"\xeb\xb9\x84\xeb\xb0\x80\xeb\xb2\x88\xed\x98\xb8" in output
        assert termios.tcgetattr(terminal_fd)[3] & termios.ECHO == 0

        os.write(terminal_fd, b"\x03")
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            waited_pid, candidate = os.waitpid(pid, os.WNOHANG)
            if waited_pid == pid:
                status = candidate
                break
            readable, _, _ = select.select([terminal_fd], [], [], 0.05)
            if readable:
                try:
                    output.extend(os.read(terminal_fd, 4096))
                except OSError:
                    pass

        assert status is not None, "single Ctrl+C during getpass did not terminate promptly"
        assert os.waitstatus_to_exitcode(status) == 130
        assert b"Traceback" not in output
        restored_attributes = termios.tcgetattr(terminal_fd)
        assert restored_attributes[3] & termios.ECHO == original_attributes[3] & termios.ECHO
    finally:
        if status is None:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
            termios.tcsetattr(terminal_fd, termios.TCSAFLUSH, original_attributes)
        os.close(terminal_fd)


@pytest.mark.asyncio
async def test_login_401_is_friendly_and_reprompts_without_printing_raw_detail() -> None:
    api = FakeApi(
        login=[ApiError(401, "UNAUTHORIZED", "provider raw secret"), None],
        profile=[PROFILE],
    )

    code, output = await run_app(api, ["bad", "wrong", "good", "right"])

    assert code == 0
    assert len([call for call in api.calls if call[0] == "login"]) == 2
    assert "아이디 또는 비밀번호" in output
    assert "provider raw secret" not in output
    assert "wrong" not in output


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        ApiError(401, "UNAUTHORIZED", "raw"),
        ApiError(409, "ONBOARDING_SESSION_EXPIRED", "raw"),
    ],
)
async def test_onboarding_auth_or_session_expiry_goes_through_login_again(error: ApiError) -> None:
    api = FakeApi(
        login=[None, None],
        profile=[ApiError(404, "PROFILE_NOT_FOUND", "raw"), PROFILE],
        start=[START],
        message=[error],
    )

    code, _ = await run_app(api, ["first", "pw1", "hello", "second", "pw2"])

    assert code == 0
    assert [call[0] for call in api.calls].count("login") == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "guidance"),
    [
        (ApiError(409, "ONBOARDING_REVISION_CONFLICT", "raw"), "최신 review"),
        (ApiError(429, "GEMINI_RATE_LIMITED", "raw"), "호출 한도"),
        (ApiError(502, "GEMINI_UNAVAILABLE", "raw"), "일시적으로 불안정"),
        (ApiError(502, "GEMINI_INVALID_RESPONSE", "raw"), "검증하지 못했습니다"),
    ],
)
async def test_recoverable_errors_keep_response_and_allow_retry(
    error: ApiError, guidance: str
) -> None:
    api = FakeApi(
        profile=[ApiError(404, "PROFILE_NOT_FOUND", "raw")],
        start=[START],
        message=[error, REVIEW],
    )

    code, output = await run_app(api, ["id", "pw", "first", "retry", "/quit"])

    assert code == 0
    assert [call[2] for call in api.calls if call[0] == "message"] == ["first", "retry"]
    assert guidance in output
    assert "raw" not in output


@pytest.mark.asyncio
async def test_rich_output_contains_engine_progress_draft_and_full_review_assessment() -> None:
    api = FakeApi(
        profile=[ApiError(404, "PROFILE_NOT_FOUND", "raw")],
        start=[START],
        message=[REVIEW],
    )

    _, output = await run_app(api, ["id", "pw", "all details", "/quit"])

    for text in (
        "google",
        "gemini-3.6-flash",
        "v1",
        "live",
        "0/8",
        "8/8",
        "백엔드 개발자",
        "누락",
        "기술 준비도",
        "경험 깊이",
        "목표 명확성",
        "실행 준비도",
        "66/100",
        "intermediate",
        "revision 4",
        "기술 근거",
        "경험 근거",
        "목표 근거",
        "실행 근거",
    ):
        assert text in output


@pytest.mark.asyncio
async def test_dynamic_strings_are_literal_rich_text_and_secrets_are_omitted() -> None:
    marked = response("conversation", EMPTY_PAYLOAD, "[bold red]가짜 경고[/bold red]")
    marked["payload"]["draft_profile"] = {
        "experience_summary": "[cyan]위조[/cyan]",
        "access_token": "must-not-print",
    }
    api = FakeApi(
        profile=[ApiError(404, "PROFILE_NOT_FOUND", "raw")],
        start=[marked],
    )

    _, output = await run_app(api, ["id", "secret", "/quit"])

    assert "[bold red]가짜 경고[/bold red]" in output
    assert "[cyan]위조[/cyan]" in output
    assert "must-not-print" not in output
    assert "secret" not in output


@pytest.mark.asyncio
async def test_verification_mismatch_stays_in_review_without_success() -> None:
    mismatched = deepcopy(PROFILE)
    mismatched["snapshot_hash"] = "b" * 64
    api = FakeApi(
        profile=[ApiError(404, "PROFILE_NOT_FOUND", "raw"), mismatched],
        start=[REVIEW],
        onboarding_result=[REVIEW],
        confirm=[COMPLETED],
    )

    code, output = await run_app(api, ["id", "pw", "/confirm", "/quit"])

    assert code == 0
    assert "검증하지 못했습니다" in output
    assert "검증 완료" not in output


@pytest.mark.asyncio
async def test_post_confirm_timeout_retries_profile_only_then_succeeds() -> None:
    api = FakeApi(
        profile=[
            ApiError(404, "PROFILE_NOT_FOUND", "raw"),
            ApiError(503, "CLIENT_TIMEOUT", "raw"),
            PROFILE,
        ],
        start=[REVIEW],
        onboarding_result=[REVIEW],
        confirm=[COMPLETED],
    )

    code, output = await run_app(api, ["id", "pw", "/confirm", "/confirm"])

    assert code == 0
    assert [call[0] for call in api.calls].count("confirm") == 1
    assert [call[0] for call in api.calls].count("profile") == 3
    assert output.index("응답 시간이 초과") < output.index("검증 완료")


@pytest.mark.asyncio
async def test_post_confirm_401_relogs_in_and_verifies_profile_without_reconfirm() -> None:
    api = FakeApi(
        login=[None, None],
        profile=[
            ApiError(404, "PROFILE_NOT_FOUND", "raw"),
            ApiError(401, "UNAUTHORIZED", "raw"),
            PROFILE,
        ],
        start=[REVIEW],
        onboarding_result=[REVIEW],
        confirm=[COMPLETED],
    )

    code, output = await run_app(
        api,
        ["first", "pw1", "/confirm", "second", "pw2"],
    )

    assert code == 0
    assert [call[0] for call in api.calls].count("login") == 2
    assert [call[0] for call in api.calls].count("confirm") == 1
    assert "검증 완료" in output


@pytest.mark.asyncio
async def test_post_confirm_mismatch_retries_profile_only_then_succeeds() -> None:
    mismatched = deepcopy(PROFILE)
    mismatched["snapshot_hash"] = "b" * 64
    api = FakeApi(
        profile=[ApiError(404, "PROFILE_NOT_FOUND", "raw"), mismatched, PROFILE],
        start=[REVIEW],
        onboarding_result=[REVIEW],
        confirm=[COMPLETED],
    )

    code, output = await run_app(api, ["id", "pw", "/confirm", "/confirm"])

    assert code == 0
    assert [call[0] for call in api.calls].count("confirm") == 1
    assert [call[0] for call in api.calls].count("profile") == 3
    assert output.index("검증하지 못했습니다") < output.index("검증 완료")


@pytest.mark.asyncio
async def test_verification_pending_rejects_corrections_and_restart_without_api_calls() -> None:
    api = FakeApi(
        profile=[
            ApiError(404, "PROFILE_NOT_FOUND", "raw"),
            ApiError(503, "CLIENT_TIMEOUT", "raw"),
        ],
        start=[REVIEW],
        onboarding_result=[REVIEW],
        confirm=[COMPLETED],
    )

    code, output = await run_app(
        api,
        ["id", "pw", "/confirm", "수정 요청", "/restart", "/help", "/quit"],
    )

    assert code == 0
    assert [call[0] for call in api.calls].count("confirm") == 1
    assert not any(call[0] in {"message", "restart"} for call in api.calls)
    assert "저장은 완료" in output


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("key", "value"),
    [("completed", False), ("step", "review")],
)
async def test_incomplete_confirmation_flags_stay_in_review_without_success(
    key: str, value: Any
) -> None:
    invalid = deepcopy(COMPLETED)
    invalid[key] = value
    api = FakeApi(
        profile=[ApiError(404, "PROFILE_NOT_FOUND", "raw"), PROFILE],
        start=[REVIEW],
        onboarding_result=[REVIEW],
        confirm=[invalid],
    )

    code, output = await run_app(api, ["id", "pw", "/confirm", "/quit"])

    assert code == 0
    assert "검증하지 못했습니다" in output
    assert "검증 완료" not in output


def test_completion_verification_covers_all_linkage_and_normalizes_time() -> None:
    profile = deepcopy(PROFILE)
    review = deepcopy(REVIEW_PAYLOAD)
    review["draft_profile"]["daily_notification_time"] = "09:30:00+09:00"
    completed = {**deepcopy(review), "stored_profile": deepcopy(profile)}

    assert _completion_matches_review(
        profile=profile,
        review_payload=review,
        completed_payload=completed,
    )

    mutations = []
    changed = deepcopy(completed)
    changed["assessment"]["score"] = 99
    mutations.append((profile, changed))
    changed_profile = deepcopy(profile)
    changed_profile["assessment_result_id"] = "different"
    mutations.append((changed_profile, completed))
    changed_profile = deepcopy(profile)
    changed_profile["assessment_source"]["rubric_version"] = "wrong"
    mutations.append((changed_profile, completed))
    changed_profile = deepcopy(profile)
    changed_profile["snapshot_hash"] = "short"
    mutations.append((changed_profile, completed))
    changed_profile = deepcopy(profile)
    changed_profile["snapshot_hash"] = "z" * 64
    changed = deepcopy(completed)
    changed["stored_profile"]["snapshot_hash"] = "z" * 64
    mutations.append((changed_profile, changed))
    changed = deepcopy(completed)
    changed["stored_profile"]["target_role"] = "다른 직무"
    mutations.append((profile, changed))
    changed = deepcopy(completed)
    changed["draft_revision"] = 5
    mutations.append((profile, changed))
    changed_profile = deepcopy(profile)
    changed_profile["draft_revision"] = 5
    mutations.append((changed_profile, completed))
    changed = deepcopy(completed)
    changed["stored_profile"]["draft_revision"] = 5
    mutations.append((profile, changed))
    changed = deepcopy(completed)
    changed["stored_profile"]["assessment_result_id"] = "different"
    mutations.append((profile, changed))
    changed = deepcopy(completed)
    changed["stored_profile"]["assessment_source"]["provider"] = "different"
    mutations.append((profile, changed))
    changed = deepcopy(completed)
    changed["stored_profile"]["snapshot_hash"] = "b" * 64
    mutations.append((profile, changed))

    for changed_profile, changed_completed in mutations:
        assert not _completion_matches_review(
            profile=changed_profile,
            review_payload=review,
            completed_payload=changed_completed,
        )


class MutatingConfirmApi(FakeApi):
    def __init__(self) -> None:
        super().__init__(
            profile=[ApiError(404, "PROFILE_NOT_FOUND", "raw"), PROFILE],
            onboarding_result=[REVIEW],
            confirm=[COMPLETED],
        )
        self.live_review = deepcopy(REVIEW)

    async def start(self) -> dict[str, Any]:
        self.calls.append(("start",))
        return self.live_review

    async def confirm(self, session_id: str, revision: int) -> dict[str, Any]:
        self.live_review["payload"]["draft_profile"]["target_role"] = "API가 변경한 값"
        await asyncio.sleep(0)
        return await super().confirm(session_id, revision)


@pytest.mark.asyncio
async def test_confirm_verifies_deepcopied_review_even_if_api_mutates_live_response() -> None:
    api = MutatingConfirmApi()

    code, output = await run_app(api, ["id", "pw", "/confirm"])

    assert code == 0
    assert "검증 완료" in output


@pytest.mark.asyncio
async def test_terminal_input_offloads_normal_and_secret_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[Any, ...]] = []

    async def fake_to_thread(function: Any, *args: Any) -> str:
        calls.append((function, *args))
        return function(*args)

    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)
    inputs = TerminalInput(normal=lambda prompt: "normal", secret=lambda prompt: "hidden")

    assert await inputs.read("ID: ") == "normal"
    assert await inputs.read_secret("PW: ") == "hidden"
    assert [call[1] for call in calls] == ["ID: ", "PW: "]
