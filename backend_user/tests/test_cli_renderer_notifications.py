from io import StringIO

from rich.console import Console

from app.cli.renderer import RichRenderer


def renderer() -> tuple[RichRenderer, StringIO]:
    stream = StringIO()
    console = Console(file=stream, force_terminal=False, width=220, color_system=None)
    return RichRenderer(console=console), stream


def test_notification_feed_renders_two_numbered_literal_safe_sections() -> None:
    view, stream = renderer()

    view.notification_feed(
        {
            "window_start": "2026-08-11",
            "window_end": "2026-08-17",
            "upcoming": [
                {
                    "id": "92000000-0000-0000-0000-000000000001",
                    "type": "daily_tasks",
                    "title": "[bold red]오늘의 일정[/bold red]",
                    "message": "[link=https://example.test]1건 예정[/link]",
                    "plan_id": "60000000-0000-0000-0000-000000000001",
                    "schedule_item_id": None,
                    "available_at": "2026-08-11T00:00:00+00:00",
                    "is_read": False,
                    "read_at": None,
                    "payload": {
                        "version": "daily_tasks.v1",
                        "date": "2026-08-11",
                        "plan_title": "[green]백엔드 로드맵[/green]",
                        "count": 1,
                        "schedules": [
                            {
                                "id": "70000000-0000-0000-0000-000000000001",
                                "kind": "task",
                                "title": "[italic]API 테스트 작성[/italic]",
                                "scheduled_at": "2026-08-11T01:00:00+00:00",
                                "status": "pending",
                            }
                        ],
                    },
                }
            ],
            "changes": [
                {
                    "id": "92000000-0000-0000-0000-000000000002",
                    "type": "roadmap_changed",
                    "title": "[magenta]일정 변경[/magenta]",
                    "message": "[underline]일정 1건 수정[/underline]",
                    "plan_id": "60000000-0000-0000-0000-000000000001",
                    "schedule_item_id": "70000000-0000-0000-0000-000000000001",
                    "available_at": "2026-08-11T00:30:00+00:00",
                    "is_read": False,
                    "read_at": None,
                    "payload": {
                        "version": "roadmap_change.v1",
                        "target": "schedule",
                        "change_kind": "update",
                        "affected_count": 1,
                        "plan_id": "60000000-0000-0000-0000-000000000001",
                        "schedule_ids": ["70000000-0000-0000-0000-000000000001"],
                        "before": None,
                        "after": None,
                    },
                },
                {
                    "id": "92000000-0000-0000-0000-000000000003",
                    "type": "plan_ended",
                    "title": "로드맵이 종료되었습니다",
                    "message": "백엔드 로드맵: 완료, 최종 진행률 100%",
                    "plan_id": "60000000-0000-0000-0000-000000000001",
                    "schedule_item_id": None,
                    "available_at": "2026-08-11T00:20:00+00:00",
                    "is_read": False,
                    "read_at": None,
                    "payload": {
                        "version": "plan_ended.v1",
                        "ended_status": "completed",
                        "final_progress": 100,
                        "plan_id": "60000000-0000-0000-0000-000000000001",
                        "plan_title": "백엔드 로드맵",
                    },
                },
                {
                    "id": "92000000-0000-0000-0000-000000000004",
                    "type": "check_in",
                    "title": "로드맵 체크인",
                    "message": "진행 상황을 확인해보세요.",
                    "plan_id": None,
                    "schedule_item_id": None,
                    "available_at": "2026-08-11T00:10:00+00:00",
                    "is_read": False,
                    "read_at": None,
                    "payload": {"version": "legacy.v1", "data": {}},
                },
            ],
            "unread_count": 4,
        }
    )

    output = stream.getvalue()
    for expected in (
        "다가오는 7일 일정",
        "최근 로드맵 변경",
        "[1]",
        "[2]",
        "[3]",
        "[4]",
        "[bold red]오늘의 일정[/bold red]",
        "[link=https://example.test]1건 예정[/link]",
        "[green]백엔드 로드맵[/green]",
        "[italic]API 테스트 작성[/italic]",
        "[magenta]일정 변경[/magenta]",
        "[underline]일정 1건 수정[/underline]",
        "완료 · 진행률 100%",
        "기존 알림",
        "미확인 4건",
    ):
        assert expected in output
    assert "없음 · 없음 · 없음건" not in output


def test_notification_feed_renders_both_empty_sections_without_selection_numbers() -> None:
    view, stream = renderer()

    view.notification_feed(
        {
            "window_start": "2026-08-11",
            "window_end": "2026-08-17",
            "upcoming": [],
            "changes": [],
            "unread_count": 0,
        }
    )

    output = stream.getvalue()
    assert "다가오는 7일 일정" in output
    assert "최근 로드맵 변경" in output
    assert output.count("표시할 미확인 알림이 없습니다.") == 2
    assert "[1]" not in output
