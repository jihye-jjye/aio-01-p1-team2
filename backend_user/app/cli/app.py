from __future__ import annotations

import asyncio
import builtins
import getpass
import os
import re
import signal
import sys
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, time, timedelta
from typing import Any, Literal, Protocol
from uuid import UUID, uuid4

from app.cli.api import ApiError, CoachApiClient
from app.cli.renderer import PROFILE_FIELDS, RichRenderer

try:
    import termios
except ImportError:  # pragma: no cover - Windows fallback
    termios = None  # type: ignore[assignment]


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


class InputPort(Protocol):
    async def read(self, prompt: str) -> str: ...
    async def read_secret(self, prompt: str) -> str: ...


class RendererPort(Protocol):
    def welcome(self) -> None: ...
    def status(self, label: str) -> Any: ...
    def authentication_help(self, *, signup: bool) -> None: ...
    def help(self, *, review: bool) -> None: ...
    def verification_help(self) -> None: ...
    def error(self, message: str) -> None: ...
    def signup_success(self, login_id: str) -> None: ...
    def response(self, onboarding_response: dict[str, Any]) -> None: ...
    def profile(self, profile: dict[str, Any], *, title: str) -> None: ...
    def success(self, profile: dict[str, Any]) -> None: ...
    def main_menu(self) -> None: ...
    def main_menu_help(self) -> None: ...
    def assistant_message(self, response: dict[str, Any]) -> None: ...
    def assistant_help(self) -> None: ...
    def assistant_report(self, response: dict[str, Any]) -> None: ...
    def saved_jobs(self, saved_jobs: list[dict[str, Any]]) -> None: ...
    def saved_job_recommendation(self, recommendation: dict[str, Any] | None) -> None: ...
    def notification_feed(self, feed: dict[str, Any]) -> None: ...
    def notices(self, notices: list[dict[str, Any]]) -> None: ...
    def today_quests(self, view: dict[str, Any]) -> None: ...
    def today_quest_help(self) -> None: ...
    def plans_summary(self, view: dict[str, Any]) -> None: ...
    def proposal(self, proposal: dict[str, Any]) -> None: ...
    def proposal_help(self) -> None: ...
    def plan(self, plan: dict[str, Any], *, task_numbers: dict[str, int]) -> None: ...
    def plan_help(self) -> None: ...
    def notice(self, message: str) -> None: ...


class TerminalInput:
    def __init__(
        self,
        *,
        normal: Callable[[str], str] | None = None,
        secret: Callable[[str], str] | None = None,
    ) -> None:
        self._normal = normal
        self._secret = secret
        self._terminal_state: tuple[int, list[Any]] | None = None

    async def read(self, prompt: str) -> str:
        return await asyncio.to_thread(self._normal or builtins.input, prompt)

    async def read_secret(self, prompt: str) -> str:
        self._capture_terminal_state()
        try:
            return await asyncio.to_thread(self._secret or getpass.getpass, prompt)
        finally:
            self.restore_terminal()

    def _capture_terminal_state(self) -> None:
        if self._secret is not None or termios is None:
            return
        try:
            terminal_fd = sys.stdin.fileno()
            attributes = termios.tcgetattr(terminal_fd)
        except (AttributeError, OSError, ValueError):
            return
        self._terminal_state = (terminal_fd, attributes)

    def restore_terminal(self) -> None:
        state = self._terminal_state
        self._terminal_state = None
        if state is None or termios is None:
            return
        terminal_fd, attributes = state
        try:
            termios.tcsetattr(terminal_fd, termios.TCSAFLUSH, attributes)
        except (OSError, ValueError):
            pass


@dataclass(frozen=True)
class VerificationPending:
    review_payload: dict[str, Any]
    completed_response: dict[str, Any]


@dataclass(frozen=True)
class ReloginRequired:
    pending: VerificationPending | None = None


@dataclass(frozen=True)
class ProfileReady:
    profile: dict[str, Any]


@dataclass(frozen=True)
class SwitchAccount:
    pass


@dataclass(frozen=True)
class AuthCredentials:
    mode: Literal["login", "signup"]
    login_id: str
    login_pw: str
    user_name: str | None = None


class CliApp:
    def __init__(
        self,
        *,
        api: ApiPort | None = None,
        input_port: InputPort | None = None,
        renderer: RendererPort | None = None,
    ) -> None:
        self.api = api or CoachApiClient()
        self.input = input_port or TerminalInput()
        self.renderer = renderer or RichRenderer()
        self._proposal_request_id: str | None = None
        self._selected_saved_job_id: str | None = None

    async def run(self) -> int:
        code = 0
        try:
            code = await self._run()
        except EOFError:
            code = 0
        except KeyboardInterrupt:
            code = 130
        finally:
            await self.api.aclose()
        return code

    async def _run(self) -> int:
        self.renderer.welcome()
        pending: VerificationPending | None = None
        auth_mode: Literal["login", "signup"] = "login"
        while True:
            credentials = await self._credentials(initial_mode=auth_mode)
            if isinstance(credentials, int):
                return credentials

            try:
                if credentials.mode == "signup":
                    with self.renderer.status("회원가입 중..."):
                        normalized_login_id = await self.api.signup(
                            credentials.login_id,
                            credentials.login_pw,
                            credentials.user_name or "",
                        )
                    self.renderer.signup_success(normalized_login_id)
                else:
                    with self.renderer.status("로그인 중..."):
                        await self.api.login(credentials.login_id, credentials.login_pw)
            except ApiError as exc:
                self.renderer.error(
                    _friendly_error(
                        exc,
                        login=credentials.mode == "login",
                        signup=credentials.mode == "signup",
                    )
                )
                auth_mode = (
                    "signup"
                    if credentials.mode == "signup" and exc.code == "VALIDATION_ERROR"
                    else "login"
                )
                continue
            auth_mode = "login"

            await self._login_notifications()

            try:
                with self.renderer.status("프로필 조회 중..."):
                    profile = await self.api.profile()
            except ApiError as exc:
                if pending is not None:
                    if _requires_login(exc):
                        self.renderer.error(_friendly_error(exc))
                        self.api.clear_access_token()
                        continue
                    self.renderer.error(_friendly_error(exc))
                    result = await self._verification_pending(pending, verify_now=False)
                    if isinstance(result, ReloginRequired):
                        pending = result.pending
                        self.api.clear_access_token()
                        continue
                    if isinstance(result, int):
                        return result
                    profile = result.profile
                    pending = None
                else:
                    if exc.code != "PROFILE_NOT_FOUND":
                        self.renderer.error(_friendly_error(exc))
                        if _requires_login(exc):
                            self.api.clear_access_token()
                        continue
                    try:
                        with self.renderer.status("온보딩 시작 중..."):
                            response = await self.api.start()
                    except ApiError as start_exc:
                        self.renderer.error(_friendly_error(start_exc))
                        if _requires_login(start_exc):
                            self.api.clear_access_token()
                        continue

                    result = await self._onboarding(response)
                    if isinstance(result, ReloginRequired):
                        pending = result.pending
                        self.api.clear_access_token()
                        continue
                    if isinstance(result, int):
                        return result
                    profile = result.profile
            else:
                if pending is not None:
                    result = await self._verification_pending(pending, profile=profile)
                    if isinstance(result, ReloginRequired):
                        pending = result.pending
                        self.api.clear_access_token()
                        continue
                    if isinstance(result, int):
                        return result
                    profile = result.profile
                    pending = None
                else:
                    self.renderer.profile(profile, title="기존 저장 프로필")

            menu_result = await self._main_menu(profile)
            if isinstance(menu_result, ReloginRequired):
                pending = menu_result.pending
                self.api.clear_access_token()
                continue
            if isinstance(menu_result, SwitchAccount):
                self.api.clear_access_token()
                pending = None
                continue
            return menu_result

    async def _login_notifications(self) -> None:
        try:
            with self.renderer.status("로그인 알림 동기화 중..."):
                feed = await self.api.login_feed()
        except ApiError:
            self.renderer.notice("로그인 알림을 불러오지 못했습니다. 프로필 조회를 계속합니다.")
            return

        self.renderer.notification_feed(feed)
        choices = _notification_choices(feed)
        if not choices:
            return

        while True:
            raw_selection = (
                await self.input.read("확인 처리할 알림 번호 (쉼표로 구분, Enter: 건너뛰기)> ")
            ).strip()
            if not raw_selection:
                return
            selected = _selected_notification_ids(raw_selection, choices)
            if selected is None:
                self.renderer.notice(
                    "표시된 알림 번호를 쉼표로 구분해 입력하거나 Enter로 건너뛰세요."
                )
                continue
            break

        for notification_id in selected:
            try:
                await self.api.mark_notification_read(notification_id)
            except ApiError:
                self.renderer.notice(
                    "알림 확인 상태를 저장하지 못했습니다. 다음 알림 처리를 계속합니다."
                )

    async def _main_menu(self, profile: dict[str, Any]) -> int | ReloginRequired | SwitchAccount:
        while True:
            self.renderer.main_menu()
            choice = (await self.input.read("메뉴> ")).strip()
            if choice in {"0", "/quit"}:
                return 0
            if choice == "/help":
                self.renderer.main_menu_help()
                continue
            if choice == "1":
                self.renderer.profile(profile, title="기존 저장 프로필")
                continue
            if choice == "2":
                result = await self._proposal_entry()
                if isinstance(result, (int, ReloginRequired)):
                    return result
                continue
            if choice == "3":
                result = await self._active_plan_entry()
                if isinstance(result, (int, ReloginRequired)):
                    return result
                continue
            if choice == "4":
                result = await self._plans_summary_entry()
                if isinstance(result, ReloginRequired):
                    return result
                continue
            if choice == "5":
                result = await self._today_quests_entry()
                if isinstance(result, (int, ReloginRequired)):
                    return result
                continue
            if choice == "6":
                result = await self._saved_jobs_entry()
                if isinstance(result, ReloginRequired):
                    return result
                continue
            if choice == "7":
                result = await self._recommend_saved_job_entry()
                if isinstance(result, (int, ReloginRequired)):
                    return result
                continue
            if choice == "8":
                result = await self._notices_entry()
                if isinstance(result, ReloginRequired):
                    return result
                continue
            if choice == "9":
                result = await self._reonboard()
                if isinstance(result, ProfileReady):
                    profile = result.profile
                    continue
                if isinstance(result, (int, ReloginRequired)):
                    return result
                continue
            if choice == "10":
                self._proposal_request_id = None
                self._selected_saved_job_id = None
                return SwitchAccount()
            if choice == "11":
                result = await self._assistant_entry()
                if isinstance(result, (int, ReloginRequired)):
                    return result
                continue
            self.renderer.main_menu_help()

    async def _assistant_entry(self) -> int | ReloginRequired | None:
        try:
            with self.renderer.status("AI 취업 코치 상담 시작 중..."):
                response = await self.api.start_assistant_session()
        except ApiError as exc:
            self.renderer.error(_friendly_error(exc))
            if _requires_login(exc):
                return ReloginRequired()
            return None

        if not isinstance(response, dict):
            self.renderer.error("상담 시작 응답을 확인할 수 없습니다. 새 상담을 시작해주세요.")
            return None
        session_id = response.get("session_id")
        revision = response.get("revision")
        if (
            not _is_canonical_uuid(session_id)
            or type(revision) is not int
            or revision != 0
            or not isinstance(response.get("assistant_message"), str)
        ):
            self.renderer.error("상담 시작 응답을 확인할 수 없습니다. 새 상담을 시작해주세요.")
            return None

        self.renderer.assistant_message(response)
        self.renderer.assistant_help()
        while True:
            text = (await self.input.read("취업 코치> ")).strip()
            if text == "/quit":
                return 0
            if text == "/help":
                self.renderer.assistant_help()
                continue
            if text == "/finish":
                if revision == 0:
                    self.renderer.notice("상담 보고서를 저장하려면 메시지를 한 번 이상 보내주세요.")
                    continue
                try:
                    with self.renderer.status("상담 보고서 저장 중..."):
                        finalized = await self.api.finalize_assistant_session(
                            session_id,
                            revision,
                        )
                except ApiError as exc:
                    self.renderer.error(_friendly_error(exc))
                    if _requires_login(exc):
                        return ReloginRequired()
                    if exc.code in {
                        "ASSISTANT_SESSION_EXPIRED",
                        "ASSISTANT_ALREADY_FINALIZED",
                        "ASSISTANT_REVISION_CONFLICT",
                        "ASSISTANT_DATA_INTEGRITY_ERROR",
                    }:
                        return None
                    continue
                if not isinstance(finalized, dict):
                    self.renderer.error("상담 보고서 응답을 확인할 수 없습니다.")
                    return None
                report = finalized.get("report")
                if (
                    finalized.get("session_id") != session_id
                    or type(finalized.get("session_revision")) is not int
                    or finalized.get("session_revision") != revision
                    or not _is_canonical_uuid(finalized.get("ai_result_id"))
                    or not isinstance(report, dict)
                    or report.get("session_id") != session_id
                    or type(report.get("session_revision")) is not int
                    or report.get("session_revision") != revision
                    or not isinstance(report.get("summary"), str)
                    or any(
                        not isinstance(report.get(field), list)
                        or not all(isinstance(item, str) for item in report[field])
                        for field in ("strengths", "improvements", "priority_actions")
                    )
                ):
                    self.renderer.error("상담 보고서 응답을 확인할 수 없습니다.")
                    return None
                self.renderer.assistant_report(finalized)
                return None
            if not text:
                self.renderer.error("상담 내용을 입력해주세요.")
                continue
            if text.startswith("/"):
                self.renderer.assistant_help()
                continue

            try:
                with self.renderer.status("AI 취업 코치 답변 생성 중..."):
                    answered = await self.api.send_assistant_message(
                        session_id,
                        revision,
                        text,
                    )
            except ApiError as exc:
                self.renderer.error(_friendly_error(exc))
                if _requires_login(exc):
                    return ReloginRequired()
                if exc.code in {
                    "ASSISTANT_SESSION_EXPIRED",
                    "ASSISTANT_ALREADY_FINALIZED",
                    "ASSISTANT_REVISION_CONFLICT",
                    "ASSISTANT_DATA_INTEGRITY_ERROR",
                }:
                    return None
                continue

            if not isinstance(answered, dict):
                self.renderer.error("상담 응답을 확인할 수 없습니다. 새 상담을 시작해주세요.")
                return None
            next_revision = answered.get("revision")
            if (
                answered.get("session_id") != session_id
                or type(next_revision) is not int
                or next_revision != revision + 1
                or not isinstance(answered.get("assistant_message"), str)
            ):
                self.renderer.error("상담 응답을 확인할 수 없습니다. 새 상담을 시작해주세요.")
                return None
            revision = next_revision
            self.renderer.assistant_message(answered)

    async def _saved_jobs_entry(self) -> ReloginRequired | None:
        try:
            with self.renderer.status("채용 공고 조회 중..."):
                saved_jobs = await self.api.saved_jobs()
        except ApiError as exc:
            self.renderer.error(_friendly_error(exc))
            if _requires_login(exc):
                return ReloginRequired()
            return None
        self.renderer.saved_jobs(saved_jobs)
        return None

    async def _notices_entry(self) -> ReloginRequired | None:
        try:
            with self.renderer.status("공지 사항 조회 중..."):
                notices = await self.api.notices()
        except ApiError as exc:
            self.renderer.error(_friendly_error(exc))
            if _requires_login(exc):
                return ReloginRequired()
            return None
        self.renderer.notices(notices)
        return None

    async def _plans_summary_entry(self) -> ReloginRequired | None:
        try:
            with self.renderer.status("로드맵 완료율 조회 중..."):
                view = await self.api.plans_summary()
        except ApiError as exc:
            self.renderer.error(_friendly_error(exc))
            if _requires_login(exc):
                return ReloginRequired()
            return None
        self.renderer.plans_summary(view if isinstance(view, dict) else {})
        return None

    async def _today_quests_entry(self) -> int | ReloginRequired | None:
        try:
            with self.renderer.status("오늘 퀘스트 조회 중..."):
                view = await self.api.today_quests()
        except ApiError as exc:
            self.renderer.error(_friendly_error(exc))
            if _requires_login(exc):
                return ReloginRequired()
            return None
        if not isinstance(view, dict) or view.get("plan_id") is None:
            self.renderer.today_quests(view if isinstance(view, dict) else {})
            return None
        return await self._today_quest_state(view)

    async def _today_quest_state(self, view: dict[str, Any]) -> int | ReloginRequired | None:
        task_selections = _today_quest_selections(view)
        self.renderer.today_quests(view)
        while True:
            command = (await self.input.read("오늘 퀘스트> ")).strip()
            if command == "/quit":
                return 0
            if command == "/back":
                return None
            if command == "/help":
                self.renderer.today_quest_help()
                continue

            task_update = _task_status_command(command)
            if task_update is None:
                self.renderer.today_quest_help()
                continue
            number, status = task_update
            task_id = task_selections.get(number)
            if task_id is None:
                self.renderer.error("현재 화면의 과제 번호를 입력해주세요.")
                continue
            try:
                with self.renderer.status("과제 상태 변경 중..."):
                    patch_result = await self.api.set_today_quest_status(str(task_id), status)
            except ApiError as exc:
                self.renderer.error(_friendly_error(exc))
                if _requires_login(exc):
                    return ReloginRequired()
                continue

            try:
                with self.renderer.status("오늘 퀘스트 다시 조회 중..."):
                    refreshed = await self.api.today_quests()
            except ApiError as exc:
                self.renderer.error(_friendly_error(exc))
                if _requires_login(exc):
                    return ReloginRequired()
                self.renderer.error(
                    "과제 상태는 변경됐지만 오늘 퀘스트를 다시 조회하지 못했습니다. "
                    "다시 조회해주세요."
                )
                continue
            if not isinstance(refreshed, dict) or refreshed.get("plan_id") is None:
                self.renderer.error(
                    "과제 상태는 변경됐지만 활성 계획이 사라져 오늘 퀘스트를 표시할 수 없습니다."
                )
                return None
            view = refreshed
            task_selections = _today_quest_selections(view)
            self.renderer.today_quests(view)
            if _today_quest_update_matches_view(patch_result, view):
                exp_delta = patch_result.get("exp_delta")
                user_exp = patch_result.get("user_exp")
                if exp_delta == 20:
                    self.renderer.notice(f"일일 목표 달성 · +20 EXP · 누적 {user_exp} EXP")
                elif exp_delta == -20:
                    self.renderer.notice(f"일일 목표 달성 취소 · -20 EXP · 누적 {user_exp} EXP")
            else:
                self.renderer.error(
                    "과제 변경 결과를 검증하지 못했습니다. 표시된 최신 오늘 퀘스트를 확인해주세요."
                )

    async def _proposal_entry(self) -> int | ReloginRequired | None:
        try:
            with self.renderer.status("대기 중인 로드맵 제안 조회 중..."):
                proposal = await self.api.pending_plan_proposal()
        except ApiError as exc:
            if _requires_login(exc):
                self.renderer.error(_friendly_error(exc))
                return ReloginRequired()
            if not _is_not_found(exc, "PLAN_PROPOSAL_NOT_FOUND"):
                self.renderer.error(_friendly_error(exc))
                return None

            confirmation = await self._yes_or_no("새 로드맵 제안을 생성합니다. 계속할까요? (y/n)")
            if type(confirmation) is int:
                return confirmation
            if not confirmation:
                return None

            request_id = self._proposal_request_id or str(uuid4())
            self._proposal_request_id = request_id
            try:
                with self.renderer.status("Gemini가 로드맵 제안을 생성하는 중..."):
                    proposal = await self.api.create_plan_proposal(
                        request_id,
                        saved_job_id=self._selected_saved_job_id,
                    )
            except ApiError as create_exc:
                if not _retain_proposal_request(create_exc):
                    self._proposal_request_id = None
                self.renderer.error(_friendly_error(create_exc))
                if _requires_login(create_exc):
                    return ReloginRequired()
                return None
            self._proposal_request_id = None

        self._proposal_request_id = None
        return await self._proposal_state(proposal, days=7)

    async def _proposal_state(
        self, proposal: dict[str, Any], *, days: int
    ) -> int | ReloginRequired | None:
        self.renderer.proposal(proposal)
        while True:
            command = (await self.input.read("제안> ")).strip()
            if command == "/quit":
                return 0
            if command == "/back":
                return None
            if command == "/help":
                self.renderer.proposal_help()
                continue
            if command == "/accept":
                result = await self._accept_proposal(proposal)
                if isinstance(result, (int, ReloginRequired)):
                    return result
                if result is None:
                    continue
                return await self._plan_state(result, days=days)
            if command == "/reject":
                try:
                    with self.renderer.status("로드맵 제안 거절 중..."):
                        await self.api.reject_plan_proposal(str(proposal["id"]))
                except (KeyError, TypeError):
                    self.renderer.error("로드맵 제안 식별자를 확인할 수 없습니다.")
                    continue
                except ApiError as exc:
                    self.renderer.error(_friendly_error(exc))
                    if _requires_login(exc):
                        return ReloginRequired()
                    if exc.code == "PLAN_PROPOSAL_NOT_PENDING":
                        return None
                    continue
                self.renderer.notice("로드맵 제안을 거절했습니다.")
                return None

            start_on: str | None = None
            if command == "/next":
                if proposal.get("has_next") is not True:
                    self.renderer.error("다음 제안 페이지가 없습니다.")
                    continue
                start_on = _next_window_start(proposal)
            elif command == "/prev":
                if proposal.get("has_previous") is not True:
                    self.renderer.error("이전 제안 페이지가 없습니다.")
                    continue
                start_on = _previous_window_start(proposal, days=days)
            elif command.startswith("/date"):
                start_on = _date_argument(command)
                if start_on is None:
                    self.renderer.proposal_help()
                    continue
            else:
                self.renderer.proposal_help()
                continue

            if start_on is None:
                self.renderer.error("제안 조회 날짜 범위를 확인할 수 없습니다.")
                continue
            try:
                proposal_id = str(proposal["id"])
                with self.renderer.status("로드맵 제안 페이지 조회 중..."):
                    proposal = await self.api.plan_proposal(
                        proposal_id, start_on=start_on, days=days
                    )
            except (KeyError, TypeError):
                self.renderer.error("로드맵 제안 식별자를 확인할 수 없습니다.")
                continue
            except ApiError as exc:
                self.renderer.error(_friendly_error(exc))
                if _requires_login(exc):
                    return ReloginRequired()
                continue
            self.renderer.proposal(proposal)

    async def _accept_proposal(
        self, proposal: dict[str, Any]
    ) -> dict[str, Any] | ReloginRequired | None:
        try:
            proposal_id = str(proposal["id"])
            with self.renderer.status("로드맵 제안 수락 중..."):
                await self.api.accept_plan_proposal(proposal_id)
            with self.renderer.status("활성 계획 검증 중..."):
                active = await self.api.active_plan()
        except (KeyError, TypeError):
            self.renderer.error("로드맵 제안 식별자를 확인할 수 없습니다.")
            return None
        except ApiError as exc:
            self.renderer.error(_friendly_error(exc))
            if _requires_login(exc):
                return ReloginRequired()
            return None
        if not _active_matches_proposal(active, proposal):
            self.renderer.error(
                "활성 계획을 검증하지 못했습니다. 활성 로드맵 메뉴에서 다시 확인해주세요."
            )
            return None
        self.renderer.notice("로드맵 제안 수락 완료")
        return active

    async def _active_plan_entry(self) -> int | ReloginRequired | None:
        try:
            with self.renderer.status("활성 계획 조회 중..."):
                plan = await self.api.active_plan()
        except ApiError as exc:
            self.renderer.error(_friendly_error(exc))
            if _requires_login(exc):
                return ReloginRequired()
            return None
        return await self._plan_state(plan, days=7)

    async def _plan_state(self, plan: dict[str, Any], *, days: int) -> int | ReloginRequired | None:
        task_selections = _visible_task_selections(plan)
        refresh_pending = False
        self.renderer.plan(
            plan,
            task_numbers=_renderer_task_numbers(task_selections),
        )
        while True:
            command = (await self.input.read("계획> ")).strip()
            if command == "/quit":
                return 0
            if command == "/back":
                return None
            if command == "/help":
                self.renderer.plan_help()
                continue
            if command == "/finish":
                if refresh_pending:
                    self.renderer.error(
                        "계획을 새로 조회한 뒤 과제 상태 변경이나 완료를 다시 시도해주세요."
                    )
                    continue
                try:
                    with self.renderer.status("계획 완료 처리 중..."):
                        completed = await self.api.complete_plan(str(plan["id"]))
                except (KeyError, TypeError):
                    self.renderer.error("활성 계획 식별자를 확인할 수 없습니다.")
                    continue
                except ApiError as exc:
                    self.renderer.error(_friendly_error(exc))
                    if _requires_login(exc):
                        return ReloginRequired()
                    continue
                completed_selections = _visible_task_selections(completed)
                self.renderer.plan(
                    completed,
                    task_numbers=_renderer_task_numbers(completed_selections),
                )
                self.renderer.notice("활성 계획을 완료했습니다.")
                return None

            task_update = _task_status_command(command)
            if task_update is not None:
                if refresh_pending:
                    self.renderer.error(
                        "계획을 새로 조회한 뒤 과제 상태 변경이나 완료를 다시 시도해주세요."
                    )
                    continue
                number, status = task_update
                task_id = task_selections.get(number)
                if task_id is None:
                    self.renderer.error("현재 화면의 과제 번호를 입력해주세요.")
                    continue
                plan_id_value = plan.get("id")
                if not isinstance(plan_id_value, str):
                    self.renderer.error("활성 계획 식별자를 확인할 수 없습니다.")
                    continue
                plan_id = plan_id_value
                try:
                    with self.renderer.status("과제 상태 변경 중..."):
                        patch_result = await self.api.set_plan_task_status(
                            plan_id, str(task_id), status
                        )
                except ApiError as exc:
                    self.renderer.error(_friendly_error(exc))
                    if _requires_login(exc):
                        return ReloginRequired()
                    continue

                task_selections = {}
                refresh_pending = True
                try:
                    with self.renderer.status("계획 다시 조회 중..."):
                        refreshed = await self.api.plan(
                            plan_id,
                            start_on=_requested_start(plan),
                            days=days,
                        )
                except ApiError as exc:
                    self.renderer.error(_friendly_error(exc))
                    if _requires_login(exc):
                        return ReloginRequired()
                    self.renderer.error(
                        "과제 상태는 변경됐지만 계획을 새로 조회하지 못했습니다. "
                        "/today 또는 /date로 다시 조회해주세요."
                    )
                    continue
                plan = refreshed
                task_selections = _visible_task_selections(plan)
                refresh_pending = False
                self.renderer.plan(
                    plan,
                    task_numbers=_renderer_task_numbers(task_selections),
                )
                if _task_update_matches_plan(patch_result, plan):
                    exp_delta = patch_result.get("exp_delta")
                    user_exp = patch_result.get("user_exp")
                    if exp_delta == 20:
                        self.renderer.notice(f"일일 목표 달성 · +20 EXP · 누적 {user_exp} EXP")
                    elif exp_delta == -20:
                        self.renderer.notice(f"일일 목표 달성 취소 · -20 EXP · 누적 {user_exp} EXP")
                else:
                    self.renderer.error(
                        "과제 변경 결과를 검증하지 못했습니다. 표시된 최신 계획을 확인해주세요."
                    )
                continue

            start_on: str | None = None
            use_active = False
            if command == "/today":
                use_active = True
            elif command == "/next":
                if plan.get("has_next") is not True:
                    self.renderer.error("다음 계획 페이지가 없습니다.")
                    continue
                start_on = _next_window_start(plan)
            elif command == "/prev":
                if plan.get("has_previous") is not True:
                    self.renderer.error("이전 계획 페이지가 없습니다.")
                    continue
                start_on = _previous_window_start(plan, days=days)
            elif command.startswith("/date"):
                start_on = _date_argument(command)
                if start_on is None:
                    self.renderer.plan_help()
                    continue
            else:
                self.renderer.plan_help()
                continue

            if not use_active and start_on is None:
                self.renderer.error("계획 조회 날짜 범위를 확인할 수 없습니다.")
                continue
            try:
                with self.renderer.status("계획 페이지 조회 중..."):
                    if use_active:
                        refreshed = await self.api.active_plan(days=days)
                    elif start_on is not None:
                        refreshed = await self.api.plan(
                            str(plan["id"]), start_on=start_on, days=days
                        )
            except (KeyError, TypeError):
                self.renderer.error("활성 계획 식별자를 확인할 수 없습니다.")
            except ApiError as exc:
                self.renderer.error(_friendly_error(exc))
                if _requires_login(exc):
                    return ReloginRequired()
            else:
                plan = refreshed
                task_selections = _visible_task_selections(plan)
                refresh_pending = False
                self.renderer.plan(
                    plan,
                    task_numbers=_renderer_task_numbers(task_selections),
                )

    async def _reonboard(self) -> int | ReloginRequired | ProfileReady | None:
        try:
            with self.renderer.status("대기 중인 로드맵 제안 확인 중..."):
                pending = await self.api.pending_plan_proposal()
        except ApiError as exc:
            if _requires_login(exc):
                self.renderer.error(_friendly_error(exc))
                return ReloginRequired()
            if not _is_not_found(exc, "PLAN_PROPOSAL_NOT_FOUND"):
                self.renderer.error(_friendly_error(exc))
                return None
        else:
            self.renderer.proposal(pending)
            self.renderer.notice(
                "대기 중인 로드맵 제안을 먼저 거절해야 프로필 재온보딩을 시작할 수 있습니다."
            )
            confirmation = await self._yes_or_no("대기 중인 제안을 거절하고 재온보딩할까요? (y/n)")
            if type(confirmation) is int:
                return confirmation
            if not confirmation:
                return None
            try:
                with self.renderer.status("대기 중인 로드맵 제안 거절 중..."):
                    await self.api.reject_plan_proposal(str(pending["id"]))
            except (KeyError, TypeError):
                self.renderer.error("로드맵 제안 식별자를 확인할 수 없습니다.")
                return None
            except ApiError as exc:
                self.renderer.error(_friendly_error(exc))
                if _requires_login(exc):
                    return ReloginRequired()
                return None

        try:
            with self.renderer.status("온보딩 시작 중..."):
                response = await self.api.start()
        except ApiError as exc:
            self.renderer.error(_friendly_error(exc))
            if _requires_login(exc):
                return ReloginRequired()
            return None
        return await self._onboarding(response)

    async def _yes_or_no(self, message: str) -> bool | int:
        self.renderer.notice(message)
        while True:
            answer = (await self.input.read("확인> ")).strip().casefold()
            if answer == "/quit":
                return 0
            if answer == "/help":
                self.renderer.notice("y 또는 yes는 진행, n 또는 no는 취소입니다.")
                continue
            if answer in {"y", "yes"}:
                return True
            if answer in {"n", "no"}:
                return False
            self.renderer.error("y/yes 또는 n/no로 답해주세요.")

    async def _credentials(
        self,
        *,
        initial_mode: Literal["login", "signup"] = "login",
    ) -> AuthCredentials | int:
        mode = initial_mode
        while True:
            prompt = "새 아이디: " if mode == "signup" else "아이디 (/signup: 회원가입): "
            login_id = (await self.input.read(prompt)).strip()
            command = self._authentication_command(login_id, unknown_is_help=True)
            if command is not None:
                if command == "quit":
                    return 0
                if command in {"login", "signup"}:
                    mode = command
                else:
                    self.renderer.authentication_help(signup=mode == "signup")
                continue

            user_name: str | None = None
            if mode == "signup":
                restart_identity = False
                while True:
                    user_name = (await self.input.read("이름: ")).strip()
                    command = self._authentication_command(user_name, unknown_is_help=True)
                    if command is None:
                        break
                    if command == "quit":
                        return 0
                    if command in {"login", "signup"}:
                        mode = command
                        restart_identity = True
                        break
                    self.renderer.authentication_help(signup=True)
                if restart_identity:
                    continue

            while True:
                password_prompt = "새 비밀번호: " if mode == "signup" else "비밀번호: "
                login_pw = await self.input.read_secret(password_prompt)
                command = self._authentication_command(login_pw)
                if command is None:
                    if mode == "signup":
                        restart_identity = False
                        while True:
                            confirmation = await self.input.read_secret("비밀번호 확인: ")
                            command = self._authentication_command(confirmation)
                            if command is not None:
                                if command == "quit":
                                    return 0
                                if command in {"login", "signup"}:
                                    mode = command
                                    restart_identity = True
                                    break
                                self.renderer.authentication_help(signup=True)
                                continue
                            if confirmation != login_pw:
                                self.renderer.error("비밀번호 확인이 일치하지 않습니다.")
                                break
                            return AuthCredentials(mode, login_id, login_pw, user_name)
                        if restart_identity:
                            break
                        continue
                    return AuthCredentials(mode, login_id, login_pw)
                if command == "quit":
                    return 0
                if command in {"login", "signup"}:
                    mode = command
                    break
                self.renderer.authentication_help(signup=mode == "signup")

    @staticmethod
    def _authentication_command(
        value: str,
        *,
        unknown_is_help: bool = False,
    ) -> Literal["login", "signup", "help", "quit"] | None:
        if value == "/quit":
            return "quit"
        if value == "/login":
            return "login"
        if value == "/signup":
            return "signup"
        if value == "/help" or (unknown_is_help and value.startswith("/")):
            return "help"
        return None

    async def _onboarding(self, response: dict[str, Any]) -> int | ReloginRequired | ProfileReady:
        self.renderer.response(response)
        while True:
            text = (await self.input.read("나> ")).strip()
            if not text:
                continue
            if text == "/quit":
                return 0
            if text == "/help":
                self.renderer.help(review=response.get("step") == "review")
                continue

            if text.startswith("/"):
                if response.get("step") == "review" and text == "/confirm":
                    result = await self._confirm(response)
                    if isinstance(result, (ReloginRequired, ProfileReady, int)):
                        return result
                    continue
                if response.get("step") == "review" and text == "/restart":
                    try:
                        with self.renderer.status("온보딩을 다시 시작하는 중..."):
                            response = await self.api.restart(str(response["session_id"]))
                    except ApiError as exc:
                        if _requires_login(exc):
                            self.renderer.error(_friendly_error(exc))
                            return ReloginRequired()
                        self.renderer.error(_friendly_error(exc))
                    else:
                        self.renderer.response(response)
                    continue
                self.renderer.help(review=response.get("step") == "review")
                continue

            try:
                with self.renderer.status("Gemini 응답을 기다리는 중..."):
                    updated = await self.api.message(str(response["session_id"]), text)
            except ApiError as exc:
                if _requires_login(exc):
                    self.renderer.error(_friendly_error(exc))
                    return ReloginRequired()
                self.renderer.error(_friendly_error(exc))
                continue
            response = updated
            self.renderer.response(response)

    async def _confirm(
        self, response: dict[str, Any]
    ) -> int | ReloginRequired | ProfileReady | None:
        review_payload = deepcopy(response.get("payload") or {})
        session_id = str(response["session_id"])
        try:
            with self.renderer.status("서버 review snapshot 조회 중..."):
                server_review = await self.api.onboarding_result(session_id)
        except (KeyError, TypeError):
            self.renderer.error("온보딩 세션 식별자를 확인할 수 없습니다.")
            return None
        except ApiError as exc:
            if _requires_login(exc):
                self.renderer.error(_friendly_error(exc))
                return ReloginRequired()
            self.renderer.error(_friendly_error(exc))
            return None

        server_payload = server_review.get("payload") if isinstance(server_review, dict) else None
        server_revision_value = server_payload.get("draft_revision") if server_payload else None
        try:
            revision = int(server_revision_value)
        except (TypeError, ValueError):
            self.renderer.error("서버 review snapshot의 revision을 확인할 수 없습니다.")
            return None

        displayed_revision = review_payload.get("draft_revision")
        try:
            if displayed_revision is not None and int(displayed_revision) != revision:
                self.renderer.error(
                    "표시된 review가 서버 snapshot과 다릅니다. 최신 review를 다시 확인해주세요."
                )
                return None
        except (TypeError, ValueError):
            self.renderer.error("표시된 review revision을 확인할 수 없습니다.")
            return None

        try:
            with self.renderer.status("review 저장 및 검증 중..."):
                completed = await self.api.confirm(session_id, revision)
        except ApiError as exc:
            if _requires_login(exc):
                self.renderer.error(_friendly_error(exc))
                return ReloginRequired()
            self.renderer.error(_friendly_error(exc))
            return None

        pending = VerificationPending(
            review_payload=review_payload,
            completed_response=deepcopy(completed),
        )
        return await self._verification_pending(pending)

    async def _verification_pending(
        self,
        pending: VerificationPending,
        *,
        profile: dict[str, Any] | None = None,
        verify_now: bool = True,
    ) -> int | ReloginRequired | ProfileReady:
        while True:
            if verify_now:
                if profile is None:
                    try:
                        with self.renderer.status("저장된 프로필 검증 중..."):
                            profile = await self.api.profile()
                    except ApiError as exc:
                        self.renderer.error(_friendly_error(exc))
                        if _requires_login(exc):
                            return ReloginRequired(pending)
                    else:
                        if _pending_matches_profile(pending, profile):
                            self.renderer.success(profile)
                            recommendation_result = await self._recommend_saved_job_entry()
                            if isinstance(recommendation_result, int):
                                return recommendation_result
                            if isinstance(recommendation_result, ReloginRequired):
                                return ReloginRequired(pending)
                            return ProfileReady(profile)
                        self.renderer.error(
                            "저장 결과를 검증하지 못했습니다. 저장된 프로필을 다시 조회해주세요."
                        )
                elif _pending_matches_profile(pending, profile):
                    self.renderer.success(profile)
                    recommendation_result = await self._recommend_saved_job_entry()
                    if isinstance(recommendation_result, int):
                        return recommendation_result
                    if isinstance(recommendation_result, ReloginRequired):
                        return ReloginRequired(pending)
                    return ProfileReady(profile)
                else:
                    self.renderer.error(
                        "저장 결과를 검증하지 못했습니다. 저장된 프로필을 다시 조회해주세요."
                    )
                profile = None
                verify_now = False

            text = (await self.input.read("검증> ")).strip()
            if text == "/quit":
                return 0
            if text == "/confirm":
                verify_now = True
                continue
            self.renderer.verification_help()

    async def _recommend_saved_job_entry(self) -> int | ReloginRequired | None:
        try:
            with self.renderer.status("희망 환경 맞춤 공고 추천 중..."):
                recommendation = await self.api.saved_job_recommendation()
        except ApiError as exc:
            self.renderer.error(_friendly_error(exc))
            if _requires_login(exc):
                return ReloginRequired()
            return None
        self.renderer.saved_job_recommendation(recommendation)
        if recommendation is None:
            return None
        job = recommendation.get("job")
        job_id = job.get("id") if isinstance(job, dict) else None
        if not _is_canonical_uuid(job_id):
            self.renderer.error("추천 공고 ID를 확인할 수 없습니다.")
            return None
        confirmation = await self._yes_or_no("이 추천 공고를 로드맵 대상으로 선택할까요? (y/n)")
        if type(confirmation) is int:
            return confirmation
        self._proposal_request_id = None
        self._selected_saved_job_id = job_id if confirmation else None
        if confirmation:
            self.renderer.notice("추천 공고를 선택했습니다. 로드맵 생성 시 이 공고를 반영합니다.")
        return None


def _is_not_found(exc: ApiError, code: str) -> bool:
    return exc.status_code == 404 and exc.code == code


def _notification_choices(feed: dict[str, Any]) -> dict[int, str]:
    upcoming = feed.get("upcoming")
    changes = feed.get("changes")
    items = (upcoming if isinstance(upcoming, list) else []) + (
        changes if isinstance(changes, list) else []
    )
    choices: dict[int, str] = {}
    for number, item in enumerate(items, start=1):
        notification_id = item.get("id") if isinstance(item, dict) else None
        if _is_canonical_uuid(notification_id):
            choices[number] = notification_id
    return choices


def _selected_notification_ids(
    raw_selection: str,
    choices: dict[int, str],
) -> list[str] | None:
    parts = [part.strip() for part in raw_selection.split(",")]
    if not parts or any(not part.isdecimal() for part in parts):
        return None
    numbers = [int(part) for part in parts]
    if any(number not in choices for number in numbers):
        return None
    return list(dict.fromkeys(choices[number] for number in numbers))


def _retain_proposal_request(exc: ApiError) -> bool:
    return bool(
        exc.retryable
        or exc.status_code == 401
        or exc.code
        in {
            "UNAUTHORIZED",
            "PLAN_GENERATION_IN_PROGRESS",
            "PLAN_GENERATION_TIMEOUT",
            "CLIENT_TIMEOUT",
            "CLIENT_NETWORK_ERROR",
        }
    )


def _requested_start(view: dict[str, Any]) -> str | None:
    value = view.get("requested_start_on")
    return value if isinstance(value, str) else None


def _next_window_start(view: dict[str, Any]) -> str | None:
    end = _parse_iso_date(view.get("requested_end_on"))
    if end is None:
        return None
    return (end + timedelta(days=1)).isoformat()


def _previous_window_start(view: dict[str, Any], *, days: int) -> str | None:
    start = _parse_iso_date(view.get("requested_start_on"))
    if start is None:
        return None
    previous = start - timedelta(days=days)
    overall_start = _parse_iso_date(view.get("starts_on"))
    if overall_start is not None and previous < overall_start:
        previous = overall_start
    return previous.isoformat()


def _date_argument(command: str) -> str | None:
    parts = command.split()
    if len(parts) != 2 or parts[0] != "/date":
        return None
    parsed = _parse_iso_date(parts[1])
    return parsed.isoformat() if parsed is not None else None


def _parse_iso_date(value: Any) -> date | None:
    if not isinstance(value, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _task_status_command(
    command: str,
) -> tuple[int, Literal["pending", "completed"]] | None:
    parts = command.split()
    if len(parts) != 2 or parts[0] not in {"/done", "/undo"}:
        return None
    try:
        number = int(parts[1])
    except ValueError:
        return None
    if number <= 0:
        return None
    status: Literal["pending", "completed"] = "completed" if parts[0] == "/done" else "pending"
    return number, status


def _visible_task_selections(plan: dict[str, Any]) -> dict[int, UUID]:
    selections: dict[int, UUID] = {}
    days = plan.get("days")
    if not isinstance(days, list):
        return selections
    for day in days:
        if not isinstance(day, dict):
            continue
        tasks = day.get("tasks")
        if not isinstance(tasks, list):
            continue
        for task in tasks:
            if not isinstance(task, dict):
                continue
            task_id = task.get("id")
            if not isinstance(task_id, str):
                continue
            try:
                parsed_task_id = UUID(task_id)
            except ValueError:
                continue
            if str(parsed_task_id) != task_id or parsed_task_id in selections.values():
                continue
            selections[len(selections) + 1] = parsed_task_id
    return selections


def _renderer_task_numbers(selections: dict[int, UUID]) -> dict[str, int]:
    return {str(task_id): number for number, task_id in selections.items()}


def _today_quest_selections(view: dict[str, Any]) -> dict[int, UUID]:
    selections: dict[int, UUID] = {}
    quests = view.get("quests")
    if not isinstance(quests, list):
        return selections
    for task in quests:
        if not isinstance(task, dict):
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str):
            continue
        try:
            parsed_task_id = UUID(task_id)
        except ValueError:
            continue
        if str(parsed_task_id) != task_id or parsed_task_id in selections.values():
            continue
        selections[len(selections) + 1] = parsed_task_id
    return selections


def _today_quest_update_matches_view(update: dict[str, Any], view: dict[str, Any]) -> bool:
    task_id = update.get("id")
    if (
        not _is_canonical_uuid(task_id)
        or view.get("completed_count") != update.get("completed_task_count")
        or view.get("total_count") != update.get("total_task_count")
        or view.get("percent") != update.get("percent")
        or view.get("achieved") is not update.get("achieved")
        or view.get("earned_exp") != update.get("earned_exp")
        or view.get("user_exp") != update.get("user_exp")
    ):
        return False
    quests = view.get("quests")
    if not isinstance(quests, list):
        return False
    for task in quests:
        if not isinstance(task, dict) or task.get("id") != task_id:
            continue
        return bool(
            task.get("plan_day") == update.get("plan_day")
            and task.get("date") == update.get("date")
            and task.get("status") == update.get("status")
            and task.get("completed_at") == update.get("completed_at")
        )
    return False


def _task_update_matches_plan(update: dict[str, Any], plan: dict[str, Any]) -> bool:
    task_id = update.get("id")
    plan_day = update.get("plan_day")
    exp_delta = update.get("exp_delta")
    user_exp = update.get("user_exp")
    if (
        not _is_canonical_uuid(task_id)
        or type(plan_day) is not int
        or plan_day <= 0
        or type(exp_delta) is not int
        or exp_delta not in (-20, 0, 20)
        or type(user_exp) is not int
        or user_exp < 0
        or plan.get("user_exp") != user_exp
        or plan.get("completed_task_count") != update.get("completed_task_count")
        or plan.get("total_task_count") != update.get("total_task_count")
        or plan.get("percent") != update.get("percent")
    ):
        return False

    days = plan.get("days")
    if not isinstance(days, list):
        return False
    for day in days:
        if not isinstance(day, dict) or day.get("plan_day") != plan_day:
            continue
        if (
            day.get("date") != update.get("date")
            or day.get("completed_task_count") != update.get("day_completed_task_count")
            or day.get("total_task_count") != update.get("day_total_task_count")
            or day.get("achieved") is not update.get("achieved")
            or day.get("achieved_at") != update.get("achieved_at")
            or day.get("earned_exp") != update.get("earned_exp")
        ):
            return False
        tasks = day.get("tasks")
        if not isinstance(tasks, list):
            return False
        for task in tasks:
            if not isinstance(task, dict) or task.get("id") != task_id:
                continue
            return bool(
                task.get("plan_day") == plan_day
                and task.get("date") == update.get("date")
                and task.get("status") == update.get("status")
                and task.get("completed_at") == update.get("completed_at")
            )
        return False
    return False


def _active_matches_proposal(active: dict[str, Any], proposal: dict[str, Any]) -> bool:
    proposal_id = proposal.get("id")
    proposal_hash = proposal.get("proposal_hash")
    title = proposal.get("title")
    starts_on = proposal.get("starts_on")
    ends_on = proposal.get("ends_on")
    total_task_count = proposal.get("total_task_count")
    starts_date = _parse_iso_date(starts_on)
    ends_date = _parse_iso_date(ends_on)
    if (
        not _is_canonical_uuid(proposal_id)
        or not isinstance(proposal_hash, str)
        or re.fullmatch(r"[0-9a-f]{64}", proposal_hash) is None
        or not isinstance(title, str)
        or not title.strip()
        or starts_date is None
        or ends_date is None
        or starts_date > ends_date
        or type(total_task_count) is not int
        or total_task_count <= 0
    ):
        return False
    return bool(
        active.get("proposal_result_id") == proposal_id
        and active.get("proposal_hash") == proposal_hash
        and active.get("title") == title
        and active.get("starts_on") == starts_on
        and active.get("ends_on") == ends_on
        and active.get("total_task_count") == total_task_count
    )


def _is_canonical_uuid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except ValueError:
        return False


def _friendly_error(
    exc: ApiError,
    *,
    login: bool = False,
    signup: bool = False,
) -> str:
    if login and exc.status_code == 401:
        return "아이디 또는 비밀번호를 확인해주세요."
    if signup and exc.code == "LOGIN_ID_ALREADY_EXISTS":
        return "이미 사용 중인 아이디입니다. 같은 아이디로 로그인해주세요."
    if signup and exc.code == "VALIDATION_ERROR":
        return "아이디는 영문자·숫자·점·밑줄·하이픈으로 4~50자, 비밀번호는 8~128자로 입력해주세요."
    if signup and (
        exc.status_code == 503 or exc.code in {"CLIENT_TIMEOUT", "CLIENT_NETWORK_ERROR"}
    ):
        return "가입 결과를 확인하지 못했습니다. 계정이 생성되었을 수 있으니 로그인해주세요."
    messages = {
        "UNAUTHORIZED": "로그인이 만료되었습니다. 다시 로그인해주세요.",
        "ONBOARDING_SESSION_EXPIRED": "온보딩 세션이 만료되었습니다. 다시 로그인해주세요.",
        "ONBOARDING_REVISION_CONFLICT": "프로필이 갱신됐습니다. 최신 review를 다시 확인해주세요.",
        "GEMINI_RATE_LIMITED": "Gemini 호출 한도에 도달했습니다. 잠시 후 다시 시도해주세요.",
        "GEMINI_UNAVAILABLE": "Gemini 연결이 일시적으로 불안정합니다. 같은 내용을 다시 보내주세요.",
        "GEMINI_CONFIGURATION_ERROR": "Gemini 서버 설정을 확인해주세요.",
        "GEMINI_INVALID_RESPONSE": "Gemini 응답을 검증하지 못했습니다. 다시 시도해주세요.",
        "GEMINI_CONTENT_BLOCKED": "안전 정책으로 해당 입력을 처리할 수 없습니다.",
        "ASSISTANT_SESSION_EXPIRED": "상담 세션이 만료되었습니다. 새 상담을 시작해주세요.",
        "ASSISTANT_SESSION_BUSY": "이전 상담 요청을 처리 중입니다. 잠시 후 다시 시도해주세요.",
        "ASSISTANT_REVISION_CONFLICT": "상담 상태가 변경되었습니다. 새 상담을 시작해주세요.",
        "ASSISTANT_SESSION_LIMIT_REACHED": "동시에 유지할 수 있는 상담은 최대 6개입니다.",
        "ASSISTANT_ALREADY_FINALIZED": "이미 종료된 상담입니다.",
        "ASSISTANT_REPORT_EMPTY": "메시지를 한 번 이상 보낸 뒤 상담을 종료해주세요.",
        "ASSISTANT_TURN_LIMIT_REACHED": "한 상담에서는 메시지를 최대 20개까지 보낼 수 있습니다.",
        "ASSISTANT_TRANSCRIPT_LIMIT_REACHED": "상담 대화 길이 한도에 도달했습니다.",
        "ASSISTANT_RESPONSE_TOO_LONG": "AI 코치 응답이 너무 깁니다. 질문을 나눠서 보내주세요.",
        "ASSISTANT_DATA_INTEGRITY_ERROR": "상담 데이터를 검증하지 못했습니다. 새 상담을 시작해주세요.",
        "PLAN_TARGET_DATE_EXPIRED": "프로필 목표일이 지나 로드맵을 생성할 수 없습니다.",
        "PLAN_HORIZON_TOO_LONG": "로드맵 기간이 너무 깁니다. 목표일을 조정해주세요.",
        "PLAN_PROPOSAL_ALREADY_PENDING": "이미 검토 대기 중인 로드맵 제안이 있습니다.",
        "ACTIVE_PLAN_EXISTS": "이미 진행 중인 활성 계획이 있습니다.",
        "PLAN_PROFILE_CHANGED": "프로필이 변경됐습니다. 새 로드맵 제안을 생성해주세요.",
        "PLAN_PROPOSAL_STALE": "로드맵 제안이 오래됐습니다. 새 제안을 생성해주세요.",
        "PLAN_GENERATION_IN_PROGRESS": "로드맵 제안을 생성 중입니다. 잠시 후 다시 확인해주세요.",
        "PLAN_GENERATION_TIMEOUT": "로드맵 생성 시간이 초과되었습니다. 다시 시도해주세요.",
        "IDEMPOTENCY_KEY_REUSED": "이 요청은 다른 작업에 이미 사용됐습니다. 새로 시도해주세요.",
        "PLAN_PROPOSAL_NOT_FOUND": "검토 대기 중인 로드맵 제안이 없습니다.",
        "PLAN_PROPOSAL_NOT_PENDING": "이미 처리된 로드맵 제안입니다.",
        "PLAN_NOT_FOUND": "활성 계획을 찾을 수 없습니다.",
        "PLAN_TASK_NOT_FOUND": "현재 계획에서 과제를 찾을 수 없습니다.",
        "PLAN_NOT_ACTIVE": "현재 활성 상태인 계획이 아닙니다.",
        "PLAN_NOT_COMPLETE": "완료하지 않은 과제가 있습니다. 모든 과제를 완료한 뒤 다시 시도해주세요.",
        "PLAN_WINDOW_OUT_OF_RANGE": "요청한 날짜는 로드맵 기간 밖입니다.",
        "PLAN_DATA_INTEGRITY_ERROR": "로드맵 데이터를 검증하지 못했습니다.",
        "TODAY_QUEST_NOT_FOUND": "오늘 퀘스트에서 해당 과제를 찾을 수 없습니다.",
        "CLIENT_TIMEOUT": "서버 응답 시간이 초과되었습니다. 다시 시도해주세요.",
        "CLIENT_NETWORK_ERROR": "서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.",
        "INVALID_RESPONSE": "서버 응답 형식을 확인할 수 없습니다. 다시 시도해주세요.",
    }
    return messages.get(exc.code, "요청을 처리하지 못했습니다. 다시 시도해주세요.")


def _requires_login(exc: ApiError) -> bool:
    return exc.status_code == 401 or exc.code in {
        "UNAUTHORIZED",
        "ONBOARDING_SESSION_EXPIRED",
    }


def _completion_matches_review(
    *,
    profile: dict[str, Any],
    review_payload: dict[str, Any],
    completed_payload: dict[str, Any],
) -> bool:
    review_revision = review_payload.get("draft_revision")
    review_draft = _dict(review_payload.get("draft_profile"))
    review_assessment = _dict(review_payload.get("assessment"))
    completed_draft = _dict(completed_payload.get("draft_profile"))
    completed_assessment = _dict(completed_payload.get("assessment"))
    stored_profile = _dict(completed_payload.get("stored_profile"))

    if set(review_draft) & set(PROFILE_FIELDS) != set(PROFILE_FIELDS):
        return False
    if completed_payload.get("draft_revision") != review_revision:
        return False
    if not _profile_matches_snapshot(completed_draft, review_draft):
        return False
    if not _profile_matches_snapshot(stored_profile, review_draft):
        return False
    if not _profile_matches_snapshot(profile, review_draft):
        return False
    if completed_assessment != review_assessment:
        return False

    persisted_assessment = {
        "assessment_score": review_assessment.get("score"),
        "assessment_level": review_assessment.get("level"),
        "assessment_summary": review_assessment.get("summary"),
        "assessment_version": review_assessment.get("version"),
    }
    for persisted in (profile, stored_profile):
        if any(persisted.get(key) != value for key, value in persisted_assessment.items()):
            return False

    expected_source = {
        "provider": review_assessment.get("provider"),
        "model": review_assessment.get("model_name"),
        "prompt_version": review_assessment.get("prompt_version"),
        "rubric_version": review_assessment.get("rubric_version"),
    }
    if any(value in (None, "") for value in expected_source.values()):
        return False
    for persisted in (profile, stored_profile):
        source = _dict(persisted.get("assessment_source"))
        if any(source.get(key) != value for key, value in expected_source.items()):
            return False

    result_id = profile.get("assessment_result_id")
    stored_result_id = stored_profile.get("assessment_result_id")
    snapshot_hash = profile.get("snapshot_hash")
    stored_hash = stored_profile.get("snapshot_hash")
    return bool(
        result_id
        and result_id == stored_result_id
        and profile.get("draft_revision") == review_revision
        and stored_profile.get("draft_revision") == review_revision
        and isinstance(snapshot_hash, str)
        and re.fullmatch(r"[0-9a-fA-F]{64}", snapshot_hash) is not None
        and snapshot_hash == stored_hash
    )


def _pending_matches_profile(
    pending: VerificationPending,
    profile: dict[str, Any],
) -> bool:
    completed = pending.completed_response
    completed_payload = completed.get("payload")
    return bool(
        completed.get("completed") is True
        and completed.get("step") == "completed"
        and isinstance(completed_payload, dict)
        and _completion_matches_review(
            profile=profile,
            review_payload=pending.review_payload,
            completed_payload=completed_payload,
        )
    )


def _profile_matches_snapshot(profile: dict[str, Any], snapshot: dict[str, Any]) -> bool:
    for field in PROFILE_FIELDS:
        actual = profile.get(field)
        expected = snapshot.get(field)
        if field == "daily_notification_time":
            actual = _normalize_time(actual)
            expected = _normalize_time(expected)
        if actual != expected:
            return False
    return True


def _normalize_time(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return time.fromisoformat(value).replace(tzinfo=None).isoformat(timespec="seconds")
        except ValueError:
            return value
    return value


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


async def _run_cli() -> int:
    app = CliApp()
    app_task = asyncio.create_task(app.run())
    loop = asyncio.get_running_loop()
    signal_handler_installed = False
    fallback_handler_installed = False
    previous_sigint_handler: Any = None
    try:
        loop.add_signal_handler(signal.SIGINT, app_task.cancel)
        signal_handler_installed = True
    except (NotImplementedError, RuntimeError):
        previous_sigint_handler = signal.getsignal(signal.SIGINT)

        def cancel_from_signal(_signum: int, _frame: Any) -> None:
            loop.call_soon_threadsafe(app_task.cancel)

        try:
            signal.signal(signal.SIGINT, cancel_from_signal)
            fallback_handler_installed = True
        except (OSError, ValueError):
            pass

    try:
        return await app_task
    except asyncio.CancelledError:
        # CliApp.run's finally block has closed the API at this point. The input/getpass
        # worker cannot be cancelled, so normal asyncio shutdown would wait forever for it.
        if isinstance(app.input, TerminalInput):
            app.input.restore_terminal()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(130)
    finally:
        if signal_handler_installed:
            loop.remove_signal_handler(signal.SIGINT)
        elif fallback_handler_installed:
            signal.signal(signal.SIGINT, previous_sigint_handler)


def main() -> None:
    raise SystemExit(asyncio.run(_run_cli()))


if __name__ == "__main__":
    main()
