from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

PROFILE_FIELDS = (
    "target_role",
    "skills",
    "experience_summary",
    "target_date",
    "target_company",
    "preferred_environment",
    "daily_notification_time",
    "assistant_style",
)

FIELD_LABELS = {
    "target_role": "목표 직무",
    "skills": "보유 기술",
    "experience_summary": "경험",
    "target_date": "목표일",
    "target_company": "희망 기업",
    "preferred_environment": "희망 환경",
    "daily_notification_time": "알림 시각",
    "assistant_style": "비서 스타일",
}

DIMENSION_LABELS = (
    ("skill_readiness", "기술 준비도"),
    ("experience_depth", "경험 깊이"),
    ("goal_clarity", "목표 명확성"),
    ("execution_readiness", "실행 준비도"),
)


class RichRenderer:
    """Render the CLI's allow-listed data without interpreting dynamic markup."""

    def __init__(self, *, console: Console | None = None) -> None:
        self.console = console or Console()

    def welcome(self) -> None:
        self.console.print(
            Panel(
                Text("Gemini 자유대화 온보딩", style="bold cyan"),
                title=Text("AI 취업 코치"),
                border_style="cyan",
            )
        )

    def status(self, label: str) -> AbstractContextManager[Any]:
        return self.console.status(Text(label), spinner="dots")

    def authentication_help(self, *, signup: bool) -> None:
        current = "회원가입" if signup else "로그인"
        self.console.print(
            Panel(
                Text(
                    "사용 가능한 명령\n"
                    f"현재 단계: {current}\n"
                    "/signup  회원가입\n"
                    "/login  로그인\n"
                    "/help  도움말\n"
                    "/quit  종료"
                ),
                border_style="blue",
            )
        )

    def help(self, *, review: bool) -> None:
        lines = [
            "사용 가능한 명령",
            "/help  도움말",
            "/quit  종료",
        ]
        if review:
            lines.extend(
                [
                    "/confirm  표시된 revision 저장",
                    "/restart  온보딩 다시 시작",
                    "그 밖의 문장은 review 수정 요청으로 전송됩니다.",
                ]
            )
        else:
            lines.append("/confirm 및 /restart는 review 단계에서만 사용할 수 있습니다.")
        self.console.print(Panel(Text("\n".join(lines)), border_style="blue"))

    def verification_help(self) -> None:
        self.console.print(
            Panel(
                Text(
                    "저장은 완료되었고 DB 검증이 대기 중입니다.\n"
                    "/confirm  저장된 프로필 다시 조회\n"
                    "/help  도움말\n"
                    "/quit  종료\n"
                    "이 상태에서는 수정 메시지와 /restart를 전송하지 않습니다."
                ),
                border_style="blue",
            )
        )

    def main_menu(self) -> None:
        self.console.print(
            Panel(
                Text(
                    "1. 프로필 보기\n"
                    "2. 로드맵 제안 생성·검토\n"
                    "3. 활성 로드맵\n"
                    "4. 오늘 퀘스트\n"
                    "5. 전체 채용 공고\n"
                    "6. 공지 사항\n"
                    "7. 프로필 재온보딩\n"
                    "8. 다른 계정으로 로그인\n"
                    "0. 종료"
                ),
                title=Text("메인 메뉴"),
                border_style="cyan",
            )
        )

    def main_menu_help(self) -> None:
        self.console.print(
            Panel(
                Text(
                    "메인 메뉴에서 번호를 입력하세요.\n"
                    "1. 프로필 보기\n"
                    "2. 로드맵 제안 생성·검토\n"
                    "3. 활성 로드맵\n"
                    "4. 오늘 퀘스트\n"
                    "5. 전체 채용 공고\n"
                    "6. 공지 사항\n"
                    "7. 프로필 재온보딩\n"
                    "8. 다른 계정으로 로그인\n"
                    "0. 종료\n"
                    "/help  도움말\n"
                    "/quit  종료"
                ),
                title=Text("메인 메뉴 도움말"),
                border_style="blue",
            )
        )

    def saved_jobs(self, saved_jobs: list[dict[str, Any]]) -> None:
        if not saved_jobs:
            self.console.print(
                Panel(
                    Text("등록된 채용 공고가 없습니다."),
                    title=Text("전체 채용 공고"),
                    border_style="yellow",
                )
            )
            return

        table = Table(
            title=Text(f"전체 채용 공고 ({len(saved_jobs)}건)"),
            show_lines=True,
        )
        table.add_column(Text("번호"), style="bold", justify="right")
        table.add_column(Text("회사"), overflow="fold")
        table.add_column(Text("직무"), overflow="fold")
        table.add_column(Text("마감일"))
        table.add_column(Text("출처"))
        table.add_column(Text("지원 URL"), overflow="fold")
        for number, saved_job in enumerate(saved_jobs, start=1):
            source_type = saved_job.get("source_type")
            source_label = {
                "url": "URL",
                "pasted_text": "직접 입력",
            }.get(source_type, _display(source_type))
            table.add_row(
                Text(str(number)),
                Text(_display(saved_job.get("company_name"))),
                Text(_display(saved_job.get("job_title"))),
                Text(_display(saved_job.get("deadline"))),
                Text(source_label),
                Text(_display(saved_job.get("source_url"))),
            )
        self.console.print(table)

    def saved_job_recommendation(self, recommendation: dict[str, Any] | None) -> None:
        if recommendation is None:
            self.console.print(
                Panel(
                    Text("추천 가능한 채용 공고가 없습니다."),
                    title=Text("희망 환경 맞춤 추천"),
                    border_style="yellow",
                )
            )
            return

        job = _mapping(recommendation.get("job"))
        matched_terms = _items(recommendation.get("matched_terms"))
        matched_text = ", ".join(str(term) for term in matched_terms) or "직접 일치 단서 없음"
        summary = Text()
        summary.append(
            f"희망 환경: {_display(recommendation.get('preferred_environment'))}\n"
        )
        summary.append(f"일치도 {_display(recommendation.get('match_score'))}점\n")
        summary.append(f"일치 단서: {matched_text}")
        self.console.print(
            Panel(
                summary,
                title=Text("희망 환경 맞춤 추천"),
                border_style="green",
            )
        )

        table = Table(show_header=False, box=None)
        table.add_column(Text("항목"), style="bold")
        table.add_column(Text("내용"), overflow="fold")
        for label, value in (
            ("회사", job.get("company_name")),
            ("직무", job.get("job_title")),
            ("마감일", job.get("deadline")),
            ("지원 URL", job.get("source_url")),
        ):
            table.add_row(Text(label), Text(_display(value)))
        self.console.print(table)

    def notices(self, notices: list[dict[str, Any]]) -> None:
        if not notices:
            self.console.print(
                Panel(
                    Text("게시 중인 공지가 없습니다."),
                    title=Text("공지 사항"),
                    border_style="yellow",
                )
            )
            return

        for index, notice in enumerate(notices, start=1):
            pinned = "고정 · " if notice.get("is_pinned") is True else ""
            self.console.print(
                Panel(
                    Text(_display(notice.get("content"))),
                    title=Text(
                        f"{pinned}{_display(notice.get('title'))} "
                        f"({_display(notice.get('published_at'))})"
                    ),
                    border_style="cyan",
                )
            )
            self.console.print(
                Text(
                    f"번호 {index} · id {_display(notice.get('id'))} · "
                    f"만료 {_display(notice.get('expires_at'))}"
                )
            )

    def today_quests(self, view: dict[str, Any]) -> None:
        plan_title = view.get("plan_title")
        if plan_title is None:
            self.console.print(
                Panel(
                    Text("진행 중인 활성 계획이 없어 오늘 퀘스트가 없습니다."),
                    title=Text("오늘 퀘스트"),
                    border_style="yellow",
                )
            )
            self.console.print(
                Text(f"날짜 {_display(view.get('date'))} · 누적 EXP {_display(view.get('user_exp'))}")
            )
            return

        self.console.print(
            Panel(
                Text(_display(plan_title)),
                title=Text("오늘 퀘스트"),
                border_style="green",
            )
        )
        self.console.print(
            Text(
                f"날짜 {_display(view.get('date'))} · "
                f"완료 {_display(view.get('completed_count'))}/"
                f"{_display(view.get('total_count'))} · "
                f"{_display(view.get('percent'))}% · "
                f"일일 달성 {'달성' if view.get('achieved') is True else '미달성'} · "
                f"획득 EXP {_display(view.get('earned_exp'))} · "
                f"누적 EXP {_display(view.get('user_exp'))}"
            )
        )

        quests = Table(title=Text("오늘 과제"), show_lines=True)
        quests.add_column(Text("번호"), style="bold", justify="right")
        quests.add_column(Text("순서"), justify="right")
        quests.add_column(Text("상태"))
        quests.add_column(Text("제목"), overflow="fold")
        quests.add_column(Text("설명"), overflow="fold")
        quests.add_column(Text("예정 시각"))
        quests.add_column(Text("완료 시각"))
        for number, task_value in enumerate(_items(view.get("quests")), start=1):
            task = _mapping(task_value)
            quests.add_row(
                Text(f"{number}번"),
                Text(f"{_display(task.get('slot'))}번"),
                Text(_display(task.get("status"))),
                Text(_display(task.get("title"))),
                Text(_display(task.get("description"))),
                Text(_display(task.get("scheduled_at"))),
                Text(_display(task.get("completed_at"))),
            )
        self.console.print(quests)

    def today_quest_help(self) -> None:
        self.console.print(
            Panel(
                Text(
                    "/done N  표시 번호 N 과제 완료\n"
                    "/undo N  표시 번호 N 과제 미완료로 되돌리기\n"
                    "/back  메인 메뉴\n"
                    "/help  도움말\n"
                    "/quit  종료"
                ),
                title=Text("오늘 퀘스트 도움말"),
                border_style="blue",
            )
        )

    def proposal(self, proposal: dict) -> None:
        self.console.print(
            Panel(
                Text(_display(proposal.get("summary"))),
                title=Text(_display(proposal.get("title"))),
                border_style="cyan",
            )
        )
        self.console.print(
            Text(
                f"상태 {_display(proposal.get('decision_status'))} · "
                f"전체 기간 {_span(proposal, 'starts_on', 'ends_on')} · "
                f"{_display(proposal.get('duration_days'))}일 · "
                f"전체 과제 {_display(proposal.get('total_task_count'))}개"
            )
        )
        self.console.print(_proposal_metadata(proposal))
        self.console.print(_page_status(proposal))

        milestones = Table(title=Text("전체 이정표"), show_lines=True)
        milestones.add_column(Text("주차"), style="bold")
        milestones.add_column(Text("기간"))
        milestones.add_column(Text("제목"), overflow="fold")
        milestones.add_column(Text("설명"), overflow="fold")
        for milestone_value in _items(proposal.get("milestones")):
            milestone = _mapping(milestone_value)
            milestones.add_row(
                Text(f"{_display(milestone.get('week_index'))}주차"),
                Text(_span(milestone, "starts_on", "ends_on")),
                Text(_display(milestone.get("title"))),
                Text(_display(milestone.get("description"))),
            )
        self.console.print(milestones)

        tasks = Table(title=Text("표시 기간 과제"), show_lines=True)
        tasks.add_column(Text("일차"), style="bold")
        tasks.add_column(Text("날짜"))
        tasks.add_column(Text("순서"), justify="right")
        tasks.add_column(Text("제목"), overflow="fold")
        tasks.add_column(Text("설명"), overflow="fold")
        for day_value in _items(proposal.get("days")):
            day = _mapping(day_value)
            for task_value in _items(day.get("tasks")):
                task = _mapping(task_value)
                tasks.add_row(
                    Text(f"{_display(day.get('plan_day'))}일차"),
                    Text(_display(day.get("date"))),
                    Text(f"{_display(task.get('slot'))}번"),
                    Text(_display(task.get("title"))),
                    Text(_display(task.get("description"))),
                )
        self.console.print(tasks)

    def proposal_help(self) -> None:
        self.console.print(
            Panel(
                Text(
                    "/next  다음 기간\n"
                    "/prev  이전 기간\n"
                    "/date YYYY-MM-DD  해당 날짜부터 보기\n"
                    "/accept  제안 수락\n"
                    "/reject  제안 거절\n"
                    "/back  메인 메뉴\n"
                    "/help  도움말\n"
                    "/quit  종료"
                ),
                title=Text("제안 화면 도움말"),
                border_style="blue",
            )
        )

    def plan(self, plan: dict, *, task_numbers: Mapping[str, int]) -> None:
        self.console.print(
            Panel(
                Text(_display(plan.get("summary"))),
                title=Text(_display(plan.get("title"))),
                border_style="green",
            )
        )
        self.console.print(
            Text(
                f"상태 {_display(plan.get('status'))} · "
                f"전체 기간 {_span(plan, 'starts_on', 'ends_on')} · "
                f"{_display(plan.get('duration_days'))}일 · "
                f"완료 {_display(plan.get('completed_task_count'))}/"
                f"{_display(plan.get('total_task_count'))} · "
                f"{_display(plan.get('percent'))}% · "
                f"누적 EXP {_display(plan.get('user_exp'))}"
            )
        )
        self.console.print(_plan_metadata(plan))
        self.console.print(_page_status(plan))

        milestones = Table(title=Text("전체 이정표"), show_lines=True)
        milestones.add_column(Text("주차"), style="bold")
        milestones.add_column(Text("기간"))
        milestones.add_column(Text("예정 시각"))
        milestones.add_column(Text("제목"), overflow="fold")
        milestones.add_column(Text("설명"), overflow="fold")
        for milestone_value in _items(plan.get("milestones")):
            milestone = _mapping(milestone_value)
            milestones.add_row(
                Text(f"{_display(milestone.get('week_index'))}주차"),
                Text(_span(milestone, "starts_on", "ends_on")),
                Text(_display(milestone.get("scheduled_at"))),
                Text(_display(milestone.get("title"))),
                Text(_display(milestone.get("description"))),
            )
        self.console.print(milestones)

        daily_goals = Table(title=Text("표시 기간 일일 목표"), show_lines=True)
        daily_goals.add_column(Text("일차"), style="bold")
        daily_goals.add_column(Text("날짜"))
        daily_goals.add_column(Text("과제 진행"))
        daily_goals.add_column(Text("달성 상태"))
        daily_goals.add_column(Text("획득 EXP"))
        daily_goals.add_column(Text("달성 시각"))
        for day_value in _items(plan.get("days")):
            day = _mapping(day_value)
            daily_goals.add_row(
                Text(f"{_display(day.get('plan_day'))}일차"),
                Text(_display(day.get("date"))),
                Text(
                    f"{_display(day.get('completed_task_count'))}/"
                    f"{_display(day.get('total_task_count'))}"
                ),
                Text("달성" if day.get("achieved") is True else "미달성"),
                Text(f"{_display(day.get('earned_exp'))} EXP"),
                Text(_display(day.get("achieved_at"))),
            )
        self.console.print(daily_goals)

        tasks = Table(title=Text("표시 기간 과제"), show_lines=True)
        tasks.add_column(Text("번호"), style="bold", justify="right")
        tasks.add_column(Text("일차"))
        tasks.add_column(Text("날짜"))
        tasks.add_column(Text("순서"), justify="right")
        tasks.add_column(Text("상태"))
        tasks.add_column(Text("제목"), overflow="fold")
        tasks.add_column(Text("설명"), overflow="fold")
        tasks.add_column(Text("예정 시각"))
        tasks.add_column(Text("완료 시각"))
        for day_value in _items(plan.get("days")):
            day = _mapping(day_value)
            for task_value in _items(day.get("tasks")):
                task = _mapping(task_value)
                task_id = task.get("id")
                number = task_numbers.get(str(task_id)) if task_id is not None else None
                tasks.add_row(
                    Text(f"{number}번" if number is not None else "없음"),
                    Text(f"{_display(task.get('plan_day', day.get('plan_day')))}일차"),
                    Text(_display(task.get("date", day.get("date")))),
                    Text(f"{_display(task.get('slot'))}번"),
                    Text(_display(task.get("status"))),
                    Text(_display(task.get("title"))),
                    Text(_display(task.get("description"))),
                    Text(_display(task.get("scheduled_at"))),
                    Text(_display(task.get("completed_at"))),
                )
        self.console.print(tasks)

    def plan_help(self) -> None:
        self.console.print(
            Panel(
                Text(
                    "/today  오늘부터 보기\n"
                    "/next  다음 기간\n"
                    "/prev  이전 기간\n"
                    "/date YYYY-MM-DD  해당 날짜부터 보기\n"
                    "/done N  표시 번호 N 과제 완료\n"
                    "/undo N  표시 번호 N 과제 미완료로 되돌리기\n"
                    "/finish  로드맵 완료\n"
                    "/back  메인 메뉴\n"
                    "/help  도움말\n"
                    "/quit  종료"
                ),
                title=Text("활성 로드맵 도움말"),
                border_style="blue",
            )
        )

    def notice(self, message: str) -> None:
        self.console.print(Panel(Text(message), title=Text("안내"), border_style="yellow"))

    def error(self, message: str) -> None:
        self.console.print(Panel(Text(message), title=Text("오류"), border_style="red"))

    def signup_success(self, login_id: str) -> None:
        self.console.print(
            Panel(
                Text(f"{login_id} 계정 생성 완료"),
                border_style="green",
            )
        )

    def response(self, onboarding_response: dict[str, Any]) -> None:
        payload = _mapping(onboarding_response.get("payload"))
        engine = _mapping(payload.get("engine"))
        engine_table = Table(title="Gemini engine", show_header=False, box=None)
        for label, key in (
            ("provider", "provider"),
            ("model", "model"),
            ("API", "api_version"),
            ("mode", "mode"),
        ):
            engine_table.add_row(Text(label, style="bold"), Text(_display(engine.get(key))))
        self.console.print(engine_table)

        self.console.print(
            Panel(
                Text(_display(onboarding_response.get("assistant_message"))),
                title=Text("Gemini"),
                border_style="cyan",
            )
        )

        answered = payload.get("answered_fields")
        answered_count = len(answered) if isinstance(answered, list) else 0
        revision = payload.get("draft_revision")
        progress = Text(
            f"수집 완료 {answered_count}/8 · revision {_display(revision)}", style="bold"
        )
        self.console.print(progress)

        draft = _mapping(payload.get("draft_profile"))
        draft_table = Table(title="현재 draft", show_lines=False)
        draft_table.add_column("항목", style="bold")
        draft_table.add_column("내용")
        for field in PROFILE_FIELDS:
            if field in draft or onboarding_response.get("step") == "review":
                draft_table.add_row(Text(FIELD_LABELS[field]), Text(_display(draft.get(field))))
        self.console.print(draft_table)

        missing = payload.get("missing_fields")
        missing_labels = []
        if isinstance(missing, list):
            missing_labels = [FIELD_LABELS.get(str(field), str(field)) for field in missing]
        self.console.print(Text("누락: " + (", ".join(missing_labels) or "없음")))

        if onboarding_response.get("step") == "review":
            self._assessment(_mapping(payload.get("assessment")))

    def _assessment(self, assessment: dict[str, Any]) -> None:
        table = Table(title="준비도 평가", show_lines=True)
        table.add_column("평가 차원", style="bold")
        table.add_column("점수", justify="right")
        table.add_column("근거")
        summary = _mapping(assessment.get("summary"))
        dimensions = _mapping(summary.get("dimensions"))
        for key, label in DIMENSION_LABELS:
            item = _mapping(dimensions.get(key))
            table.add_row(
                Text(label),
                Text(_display(item.get("score"))),
                Text(_display(item.get("reason"))),
            )
        self.console.print(table)
        self.console.print(
            Text(
                "총점 "
                f"{_display(assessment.get('score'))}/100 · "
                f"level {_display(assessment.get('level'))}"
            )
        )

    def profile(self, profile: dict[str, Any], *, title: str) -> None:
        table = Table(title=Text(title), show_lines=False)
        table.add_column("항목", style="bold")
        table.add_column("내용", overflow="fold")
        for field in PROFILE_FIELDS:
            table.add_row(Text(FIELD_LABELS[field]), Text(_display(profile.get(field))))

        source = _mapping(profile.get("assessment_source"))
        for label, value in (
            ("준비도", f"{_display(profile.get('assessment_score'))}/100"),
            ("level", profile.get("assessment_level")),
            ("assessment_result_id", profile.get("assessment_result_id")),
            ("draft_revision", profile.get("draft_revision")),
            ("snapshot_hash", profile.get("snapshot_hash")),
            ("provider", source.get("provider")),
            ("실제 Gemini 모델", source.get("model")),
            ("prompt_version", source.get("prompt_version")),
            ("rubric_version", source.get("rubric_version")),
        ):
            table.add_row(Text(label), Text(_display(value)))
        self.console.print(table)

    def success(self, profile: dict[str, Any]) -> None:
        self.console.print(
            Panel(
                Text("검증 완료: 표시된 review와 DB 재조회 결과가 일치합니다."),
                border_style="green",
            )
        )
        self.profile(profile, title="DB 재조회 프로필")


Renderer = RichRenderer


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _span(value: dict[str, Any], start_key: str, end_key: str) -> str:
    return f"{_display(value.get(start_key))} ~ {_display(value.get(end_key))}"


def _page_status(value: dict[str, Any]) -> Text:
    previous = "있음" if value.get("has_previous") is True else "없음"
    following = "있음" if value.get("has_next") is True else "없음"
    return Text(
        f"표시 기간 {_span(value, 'requested_start_on', 'requested_end_on')} · "
        f"이전 페이지: {previous} · 다음 페이지: {following}"
    )


def _metadata(title: str, rows: tuple[tuple[str, Any], ...]) -> Table:
    table = Table(title=Text(title), show_header=False, box=None)
    table.add_column(Text("항목"), style="bold")
    table.add_column(Text("값"), overflow="fold")
    for label, value in rows:
        table.add_row(Text(label), Text(_display(value)))
    return table


def _proposal_metadata(proposal: dict[str, Any]) -> Table:
    return _metadata(
        "제안 메타데이터",
        (
            ("proposal_id", proposal.get("id")),
            ("request_id", proposal.get("request_id")),
            ("생성일", proposal.get("generated_on")),
            ("proposal_hash", proposal.get("proposal_hash")),
            ("profile_hash", proposal.get("profile_hash")),
            ("assessment_result_id", proposal.get("assessment_result_id")),
            ("schema_version", proposal.get("schema_version")),
            ("model_name", proposal.get("model_name")),
            ("prompt_version", proposal.get("prompt_version")),
            ("api_version", proposal.get("api_version")),
            ("outline_prompt_version", proposal.get("outline_prompt_version")),
            ("tasks_prompt_version", proposal.get("tasks_prompt_version")),
            ("applied_plan_id", proposal.get("applied_plan_id")),
            ("decided_at", proposal.get("decided_at")),
            ("created_at", proposal.get("created_at")),
        ),
    )


def _plan_metadata(plan: dict[str, Any]) -> Table:
    return _metadata(
        "로드맵 메타데이터",
        (
            ("plan_id", plan.get("id")),
            ("proposal_result_id", plan.get("proposal_result_id")),
            ("proposal_hash", plan.get("proposal_hash")),
            ("profile_hash", plan.get("profile_hash")),
            ("assessment_result_id", plan.get("assessment_result_id")),
            ("schema_version", plan.get("schema_version")),
            ("model_name", plan.get("model_name")),
            ("prompt_version", plan.get("prompt_version")),
            ("api_version", plan.get("api_version")),
            ("outline_prompt_version", plan.get("outline_prompt_version")),
            ("tasks_prompt_version", plan.get("tasks_prompt_version")),
            ("activated_at", plan.get("activated_at")),
            ("ended_at", plan.get("ended_at")),
            ("restart_offer_status", plan.get("restart_offer_status")),
            ("restart_prompted_at", plan.get("restart_prompted_at")),
        ),
    )


def _display(value: Any) -> str:
    if value is None:
        return "없음"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)
