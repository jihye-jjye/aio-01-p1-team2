from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from app.coach.models import (
    AssistantStyle,
    JobRecommendationToolResult,
    ScheduleLookupToolResult,
)

KST = ZoneInfo("Asia/Seoul")


def render_job_recommendation(result: JobRecommendationToolResult) -> str:
    if result.status == "no_eligible_jobs":
        return "[공고 추천 사실]\n현재 지원 가능한 저장 공고가 없습니다."

    job = result.job
    if job is None or result.match_score is None:
        raise ValueError("found 추천 결과의 사실 정보가 없습니다.")
    deadline = job.deadline.isoformat() if job.deadline is not None else "마감일 미정"
    url = job.source_url or "원문 URL 없음"
    matched = ", ".join(result.matched_terms) if result.matched_terms else "확인된 항목 없음"
    return "\n".join(
        [
            "[공고 추천 사실]",
            f"회사: {_display_text(job.company_name)}",
            f"직무: {_display_text(job.job_title)}",
            f"마감일: {deadline}",
            f"원문: {_display_text(url)}",
            f"DB 확인 시각: {_kst_datetime(result.observed_at)}",
            "[추천 판단]",
            f"매칭 점수: {result.match_score}/100",
            f"매칭 키워드: {_display_text(matched)}",
            f"추천 이유: {_display_text(result.reason or '')}",
            f"판단 방식: {result.recommendation_source}",
        ]
    )


def render_schedule_lookup(result: ScheduleLookupToolResult) -> str:
    header = [
        "[일정 조회 사실]",
        f"조회 기간: {result.range_start.isoformat()} ~ {result.range_end.isoformat()} (KST)",
        f"DB 확인 시각: {_kst_datetime(result.observed_at)}",
    ]
    if result.status == "no_active_plan":
        return "\n".join([*header, "현재 활성 로드맵이 없습니다."])
    if result.plan_id is None or result.plan_title is None:
        raise ValueError("일정 결과의 계획 정보가 없습니다.")
    header.append(f"계획: {_display_text(result.plan_title)} ({result.plan_id})")
    if result.status == "empty":
        return "\n".join([*header, "해당 기간에 조회 가능한 일정이 없습니다."])

    lines = header
    for item in sorted(
        result.items,
        key=lambda value: (value.scheduled_at, value.plan_day or 0, value.slot or 0, value.id),
    ):
        position = ""
        if item.plan_day is not None:
            position = f" · plan day {item.plan_day}"
        if item.slot is not None:
            position += f" · slot {item.slot}"
        description = f" — {_display_text(item.description)}" if item.description else ""
        lines.append(
            f"- {_kst_datetime(item.scheduled_at)} · {item.kind} · {_display_text(item.title)} "
            f"[{item.status}]{position}{description}"
        )
    return "\n".join(lines)


def coaching_fallback(*, style: AssistantStyle, has_tools: bool) -> str:
    if style == "direct":
        if has_tools:
            return (
                "준비가 부족한 상태에서 정보만 읽고 멈추면 기회는 그대로 지나갑니다. "
                "핑계는 결과를 바꾸지 못합니다. 지금 확인된 사실에서 가장 급한 행동 하나를 "
                "정하고 바로 끝내세요."
            )
        return (
            "현재 준비 상태를 냉정하게 보셔야 합니다. 생각만 길어지는 동안 결과는 달라지지 "
            "않습니다. 지금 통제할 수 있는 행동 하나를 정해 바로 실행하세요."
        )
    if has_tools:
        return (
            "지금 확인된 사실만으로도 다음 행동을 정할 수 있어요. 가장 부담이 적고 효과가 큰 "
            "한 가지부터 오늘 바로 시작해보세요."
        )
    return (
        "지금 고민을 구체적으로 말해주신 것만으로도 좋은 출발이에요. 할 수 있는 행동을 작게 "
        "나눠 한 가지부터 함께 시작해봐요."
    )


def _kst_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("사실 시각에는 timezone 정보가 필요합니다.")
    return value.astimezone(KST).strftime("%Y-%m-%d %H:%M KST")


def _display_text(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)[1:-1]
