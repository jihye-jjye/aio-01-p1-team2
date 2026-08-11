from copy import deepcopy
from io import StringIO

from rich.console import Console

from app.cli.renderer import RichRenderer

SECRET_RAW_FIELDS = (
    "access_token",
    "refresh_token",
    "api_key",
    "provider_raw_response",
    "redis_key",
    "redis_checkpoint",
    "checkpoint",
    "raw_error",
    "detail",
    "details",
)


def renderer() -> tuple[RichRenderer, StringIO]:
    stream = StringIO()
    console = Console(file=stream, force_terminal=False, width=220, color_system=None)
    return RichRenderer(console=console), stream


def secret_raw_fields(location: str) -> dict[str, str]:
    return {field: f"MUST_NOT_PRINT::{location}::{field}" for field in SECRET_RAW_FIELDS}


def proposal_view() -> dict:
    return {
        "id": "proposal-visible-id",
        "request_id": "request-visible-id",
        "decision_status": "pending",
        "title": "[bold red]제안 제목[/bold red]",
        "summary": "[link=https://example.test]제안 요약[/link]",
        "generated_on": "2026-08-10",
        "starts_on": "2026-08-10",
        "ends_on": "2026-09-06",
        "duration_days": 28,
        "milestones": [
            {
                "week_index": 1,
                "starts_on": "2026-08-10",
                "ends_on": "2026-08-16",
                "title": "[magenta]첫 이정표[/magenta]",
                "description": "[italic]핵심 결과[/italic]",
            }
        ],
        "days": [
            {
                "plan_day": 8,
                "date": "2026-08-17",
                "tasks": [
                    {
                        "slot": 1,
                        "title": "[green]API 과제[/green]",
                        "description": "[underline]테스트 작성[/underline]",
                    }
                ],
            }
        ],
        "total_task_count": 56,
        "proposal_hash": "proposal-hash",
        "profile_hash": "profile-hash",
        "assessment_result_id": "assessment-id",
        "schema_version": "profile-plan-proposal-v1",
        "model_name": "model-name",
        "prompt_version": "profile-plan-proposal-v1",
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


def plan_view() -> dict:
    return {
        "id": "plan-visible-id",
        "proposal_result_id": "proposal-result-visible-id",
        "proposal_hash": "proposal-hash",
        "profile_hash": "profile-hash",
        "assessment_result_id": "assessment-id",
        "title": "[bold red]활성 계획[/bold red]",
        "summary": "[link=https://example.test]계획 요약[/link]",
        "starts_on": "2026-08-10",
        "ends_on": "2026-09-06",
        "duration_days": 28,
        "status": "active",
        "milestones": [
            {
                "id": "milestone-secret-id",
                "week_index": 1,
                "starts_on": "2026-08-10",
                "ends_on": "2026-08-16",
                "scheduled_at": "2026-08-16T09:00:00+09:00",
                "title": "[magenta]첫 이정표[/magenta]",
                "description": "[italic]핵심 결과[/italic]",
            }
        ],
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
                        "id": "task-id-alpha",
                        "plan_day": 8,
                        "slot": 1,
                        "date": "2026-08-17",
                        "scheduled_at": "2026-08-17T09:00:00+09:00",
                        "title": "[green]API 과제[/green]",
                        "description": "[underline]테스트 작성[/underline]",
                        "status": "completed",
                        "completed_at": "2026-08-17T10:00:00+09:00",
                    },
                    {
                        "id": "task-id-beta",
                        "plan_day": 8,
                        "slot": 2,
                        "date": "2026-08-17",
                        "scheduled_at": "2026-08-17T11:00:00+09:00",
                        "title": "두 번째 과제",
                        "description": "반복 연습",
                        "status": "pending",
                        "completed_at": None,
                    },
                ],
            }
        ],
        "total_task_count": 3,
        "completed_task_count": 1,
        "percent": 33,
        "user_exp": 20,
        "schema_version": "profile-plan-proposal-v1",
        "model_name": "model-name",
        "prompt_version": "profile-plan-proposal-v1",
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


def test_main_menu_and_help_expose_only_the_documented_choices() -> None:
    view, stream = renderer()

    view.main_menu()
    view.main_menu_help()

    output = stream.getvalue()
    for choice in (
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
        "/help",
        "/quit",
    ):
        assert choice in output
    for undocumented in (
        "/profile",
        "/proposal",
        "/generate",
        "/plan",
        "/onboarding",
        "/switch",
    ):
        assert undocumented not in output


def test_assistant_message_help_and_report_render_only_safe_literal_fields() -> None:
    view, stream = renderer()

    view.assistant_message(
        {
            "assistant_style": "friendly",
            "intent": "schedule_lookup",
            "assistant_message": "[bold red]내일 할 일[/bold red]을 정리했어요.",
            "tool_results": [{"provider_raw_response": "MUST_NOT_PRINT::tool"}],
        }
    )
    view.assistant_help()
    view.assistant_report(
        {
            "ai_result_id": "report-visible-id",
            "report": {
                "summary": "[green]상담 요약[/green]",
                "strengths": ["목표가 구체적입니다."],
                "improvements": ["지원 근거를 보강하세요."],
                "priority_actions": ["오늘 지원서 한 문단을 고치세요."],
                "source_session_hash": "MUST_NOT_PRINT::hash",
                "engine": {"provider_raw_response": "MUST_NOT_PRINT::provider"},
            },
        }
    )

    output = stream.getvalue()
    for expected in (
        "친절형",
        "일정 조회",
        "[bold red]내일 할 일[/bold red]을 정리했어요.",
        "/finish  상담 종료 및 보고서 저장",
        "report-visible-id",
        "[green]상담 요약[/green]",
        "목표가 구체적입니다.",
        "지원 근거를 보강하세요.",
        "오늘 지원서 한 문단을 고치세요.",
    ):
        assert expected in output
    assert "MUST_NOT_PRINT" not in output


def test_assistant_renderer_fails_closed_for_malformed_display_fields() -> None:
    view, stream = renderer()

    view.assistant_message(
        {
            "assistant_style": {"provider_raw_response": "MUST_NOT_PRINT::style"},
            "intent": ["MUST_NOT_PRINT::intent"],
            "assistant_message": {"redis_key": "MUST_NOT_PRINT::message"},
        }
    )
    view.assistant_report(
        {
            "ai_result_id": {"checkpoint": "MUST_NOT_PRINT::id"},
            "report": {
                "summary": {"provider_raw_response": "MUST_NOT_PRINT::summary"},
                "strengths": [{"redis_checkpoint": "MUST_NOT_PRINT::strength"}],
                "improvements": ["안전한 보완점", {"raw_error": "MUST_NOT_PRINT::error"}],
                "priority_actions": "MUST_NOT_PRINT::not-a-list",
            },
        }
    )

    output = stream.getvalue()
    assert "안전한 보완점" in output
    assert "MUST_NOT_PRINT" not in output


def test_saved_jobs_renders_summary_fields_as_literal_text_and_handles_empty_list() -> None:
    view, stream = renderer()

    view.saved_jobs(
        [
            {
                "source_type": "url",
                "source_url": "https://example.test/[link]",
                "company_name": "[bold red]예시회사[/bold red]",
                "job_title": "[green]백엔드 개발자[/green]",
                "deadline": "2026-08-31",
            }
        ]
    )
    view.saved_jobs([])

    output = stream.getvalue()
    for expected in (
        "전체 채용 공고 (1건)",
        "[bold red]예시회사[/bold red]",
        "[green]백엔드 개발자[/green]",
        "2026-08-31",
        "https://example.test/[link]",
        "등록된 채용 공고가 없습니다.",
    ):
        assert expected in output


def test_saved_job_recommendation_renders_score_terms_and_job_as_literal_text() -> None:
    view, stream = renderer()

    view.saved_job_recommendation(
        {
            "preferred_environment": "[bold]원격 근무[/bold]",
            "match_score": 50,
            "matched_terms": ["원격"],
            "recommendation_source": "llm",
            "reason": "[blue]전체 프로필 기준 추천[/blue]",
            "job": {
                "company_name": "[red]예시회사[/red]",
                "job_title": "백엔드 개발자",
                "deadline": "2026-08-31",
                "source_url": "https://example.test/[link]",
            },
        }
    )
    view.saved_job_recommendation(None)

    output = stream.getvalue()
    for expected in (
        "희망 환경 맞춤 추천",
        "[bold]원격 근무[/bold]",
        "일치도 50점",
        "일치 단서: 원격",
        "판단 방식: Gemini",
        "[blue]전체 프로필 기준 추천[/blue]",
        "[red]예시회사[/red]",
        "https://example.test/[link]",
        "추천 가능한 채용 공고가 없습니다.",
    ):
        assert expected in output


def test_saved_job_recommendation_identifies_keyword_fallback() -> None:
    view, stream = renderer()

    view.saved_job_recommendation(
        {
            "preferred_environment": "원격 근무",
            "match_score": 50,
            "matched_terms": ["원격"],
            "recommendation_source": "keyword_fallback",
            "reason": "Gemini 판단을 사용할 수 없어 키워드로 추천했습니다.",
            "job": {
                "company_name": "예시회사",
                "job_title": "백엔드 개발자",
                "deadline": None,
                "source_url": None,
            },
        }
    )

    output = stream.getvalue()
    assert "판단 방식: 키워드 대체" in output
    assert "Gemini 판단을 사용할 수 없어 키워드로 추천했습니다." in output


def test_notices_renders_pinned_and_unpinned_as_literal_text() -> None:
    view, stream = renderer()

    view.notices(
        [
            {
                "id": "91000000-0000-0000-0000-000000000001",
                "title": "[bold red]서비스 점검[/bold red]",
                "content": "[link=https://example.test]일시 점검 예정[/link]",
                "is_pinned": True,
                "published_at": "2026-08-09T09:00:00+09:00",
                "expires_at": None,
            },
            {
                "id": "91000000-0000-0000-0000-000000000002",
                "title": "일반 공지",
                "content": "내용",
                "is_pinned": False,
                "published_at": "2026-08-08T09:00:00+09:00",
                "expires_at": "2026-09-01T00:00:00+09:00",
            },
        ]
    )
    view.notices([])

    output = stream.getvalue()
    for expected in (
        "고정 · [bold red]서비스 점검[/bold red]",
        "[link=https://example.test]일시 점검 예정[/link]",
        "일반 공지",
        "게시 중인 공지가 없습니다.",
    ):
        assert expected in output


def test_today_quests_renders_active_plan_summary_and_quest_table() -> None:
    view, stream = renderer()

    view.today_quests(
        {
            "date": "2026-08-17",
            "plan_id": "60000000-0000-0000-0000-000000000001",
            "plan_title": "[green]백엔드 로드맵[/green]",
            "quests": [
                {
                    "id": "70000000-0000-0000-0000-000000000001",
                    "plan_day": 8,
                    "slot": 1,
                    "date": "2026-08-17",
                    "scheduled_at": "2026-08-17T09:30:00+09:00",
                    "title": "[bold]API 과제[/bold]",
                    "description": "테스트 작성",
                    "status": "pending",
                    "completed_at": None,
                }
            ],
            "completed_count": 0,
            "total_count": 1,
            "percent": 0,
            "achieved": False,
            "earned_exp": 0,
            "user_exp": 20,
        }
    )

    output = stream.getvalue()
    for expected in (
        "[green]백엔드 로드맵[/green]",
        "완료 0/1",
        "0%",
        "일일 달성 미달성",
        "누적 EXP 20",
        "[bold]API 과제[/bold]",
    ):
        assert expected in output


def test_today_quests_renders_empty_state_when_no_active_plan() -> None:
    view, stream = renderer()

    view.today_quests(
        {
            "date": "2026-08-17",
            "plan_id": None,
            "plan_title": None,
            "quests": [],
            "completed_count": 0,
            "total_count": 0,
            "percent": 0,
            "achieved": False,
            "earned_exp": 0,
            "user_exp": 0,
        }
    )

    output = stream.getvalue()
    assert "활성 계획이 없어 오늘 퀘스트가 없습니다." in output
    assert "누적 EXP 0" in output


def test_today_quest_help_exposes_only_documented_commands() -> None:
    view, stream = renderer()

    view.today_quest_help()

    output = stream.getvalue()
    for expected in (
        "/done N",
        "/undo N",
        "/back",
        "/help",
        "/quit",
    ):
        assert expected in output
    for undocumented in ("/next", "/prev", "/date", "/accept", "/finish"):
        assert undocumented not in output


def test_plans_summary_renders_aggregate_and_per_plan_rows_as_literal_markup() -> None:
    view, stream = renderer()

    view.plans_summary(
        {
            "user_exp": 40,
            "plan_count": 2,
            "aggregate_total_task_count": 6,
            "aggregate_completed_task_count": 5,
            "aggregate_percent": 83,
            "plans": [
                {
                    "id": "60000000-0000-0000-0000-000000000001",
                    "title": "[bold red]백엔드 로드맵[/bold red]",
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
    )

    output = stream.getvalue()
    for expected in (
        "로드맵 2개",
        "전체 과제 5/6 완료",
        "통합 완료율 83%",
        "누적 EXP 40",
        "[bold red]백엔드 로드맵[/bold red]",
        "이전 로드맵",
        "66%",
        "100%",
        "2026-08-10 ~ 2026-08-16",
    ):
        assert expected in output
    assert "[/bold red]" in output


def test_plans_summary_renders_empty_state() -> None:
    view, stream = renderer()

    view.plans_summary(
        {
            "user_exp": 7,
            "plan_count": 0,
            "aggregate_total_task_count": 0,
            "aggregate_completed_task_count": 0,
            "aggregate_percent": 0,
            "plans": [],
        }
    )

    output = stream.getvalue()
    assert "생성된 로드맵이 없습니다." in output
    assert "누적 EXP 7" in output


def test_proposal_renders_metadata_window_milestones_tasks_and_literal_markup() -> None:
    view, stream = renderer()

    view.proposal(proposal_view())

    output = stream.getvalue()
    for expected in (
        "pending",
        "2026-08-10 ~ 2026-09-06",
        "28일",
        "전체 과제 56개",
        "2026-08-17 ~ 2026-08-23",
        "이전 페이지: 있음",
        "다음 페이지: 있음",
        "1주차",
        "8일차",
        "1번",
        "[bold red]제안 제목[/bold red]",
        "[link=https://example.test]제안 요약[/link]",
        "[magenta]첫 이정표[/magenta]",
        "[green]API 과제[/green]",
    ):
        assert expected in output


def test_proposal_help_exposes_only_proposal_commands() -> None:
    view, stream = renderer()

    view.proposal_help()

    output = stream.getvalue()
    for command in (
        "/next",
        "/prev",
        "/date YYYY-MM-DD",
        "/accept",
        "/reject",
        "/back",
        "/help",
        "/quit",
    ):
        assert command in output
    for plan_only in ("/today", "/done N", "/undo N", "/finish"):
        assert plan_only not in output


def test_plan_uses_supplied_task_numbers_and_never_displays_task_ids() -> None:
    view, stream = renderer()

    view.plan(
        plan_view(),
        task_numbers={"task-id-alpha": 41, "task-id-beta": 92},
    )

    output = stream.getvalue()
    for expected in (
        "active",
        "완료 1/3 · 33%",
        "누적 EXP 20",
        "일일 목표",
        "1/2",
        "미달성",
        "0 EXP",
        "2026-08-17 ~ 2026-08-23",
        "이전 페이지: 있음",
        "다음 페이지: 있음",
        "41번",
        "92번",
        "completed",
        "pending",
        "[bold red]활성 계획[/bold red]",
        "[green]API 과제[/green]",
    ):
        assert expected in output
    assert "task-id-alpha" not in output
    assert "task-id-beta" not in output
    assert "milestone-secret-id" not in output


def test_plan_help_exposes_only_plan_commands() -> None:
    view, stream = renderer()

    view.plan_help()

    output = stream.getvalue()
    for command in (
        "/today",
        "/next",
        "/prev",
        "/date YYYY-MM-DD",
        "/done N",
        "/undo N",
        "/finish",
        "/back",
        "/help",
        "/quit",
    ):
        assert command in output
    assert "/accept" not in output
    assert "/reject" not in output


def test_notice_treats_server_message_as_literal_text() -> None:
    view, stream = renderer()

    view.notice("[bold red]서버 메시지[/bold red]")

    assert "[bold red]서버 메시지[/bold red]" in stream.getvalue()


def test_proposal_and_plan_ignore_secret_raw_fields_at_top_and_nested_levels() -> None:
    proposal = deepcopy(proposal_view())
    proposal.update(secret_raw_fields("proposal-top"))
    proposal["milestones"][0].update(secret_raw_fields("proposal-milestone"))
    proposal["days"][0].update(secret_raw_fields("proposal-day"))
    proposal["days"][0]["tasks"][0].update(secret_raw_fields("proposal-task"))

    plan = deepcopy(plan_view())
    plan.update(secret_raw_fields("plan-top"))
    plan["milestones"][0].update(secret_raw_fields("plan-milestone"))
    plan["days"][0].update(secret_raw_fields("plan-day"))
    plan["days"][0]["tasks"][0].update(secret_raw_fields("plan-task"))

    view, stream = renderer()
    view.proposal(proposal)
    view.plan(
        plan,
        task_numbers={"task-id-alpha": 41, "task-id-beta": 92},
    )

    output = stream.getvalue()
    assert "MUST_NOT_PRINT" not in output
    for field in SECRET_RAW_FIELDS:
        assert field not in output
    for literal_dynamic_text in (
        "[bold red]제안 제목[/bold red]",
        "[green]API 과제[/green]",
        "[bold red]활성 계획[/bold red]",
    ):
        assert literal_dynamic_text in output
