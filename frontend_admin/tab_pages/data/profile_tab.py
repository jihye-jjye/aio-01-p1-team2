from __future__ import annotations

from datetime import date, datetime
from html import escape
from typing import Any, Mapping

import streamlit as st


_EMPTY_VALUE = "미입력"

def _value(profile: Mapping[str, Any], key: str) -> str:
    value = profile.get(key)
    if value is None or value == "":
        return _EMPTY_VALUE
    return str(value)


def _target_date(profile: Mapping[str, Any]) -> date | None:
    value = profile.get("target_date")
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _days_until(target_date: date | None) -> str:
    if target_date is None:
        return _EMPTY_VALUE

    remaining_days = (target_date - date.today()).days
    if remaining_days < 0:
        return f"{abs(remaining_days)}일 경과"
    if remaining_days == 0:
        return "오늘"
    return f"D-{remaining_days}"


def _skills(profile: Mapping[str, Any]) -> list[str]:
    raw_skills = profile.get("skills") or []
    if not isinstance(raw_skills, list):
        return []
    return [str(skill).strip() for skill in raw_skills if str(skill).strip()]


def show_profile(profile: Mapping[str, Any] | None) -> None:
    """Render a readable, at-a-glance profile for the admin user detail page."""
    if not profile:
        st.info("아직 프로필 온보딩을 완료하지 않은 사용자입니다.")
        return

    target_date = _target_date(profile)
    target_role = _value(profile, "target_role")

    st.subheader("취업 목표")
    goal_col, company_col, date_col = st.columns(3)
    goal_col.metric("목표 직무", target_role)
    company_col.metric("목표 기업", _value(profile, "target_company"))
    date_col.metric("목표일까지", _days_until(target_date))
    if target_date:
        date_col.caption(f"목표일: {target_date:%Y.%m.%d}")

    st.divider()
    detail_col, setting_col = st.columns([1.5, 1])

    with detail_col:
        st.subheader("준비 현황")
        st.caption("보유 기술")
        skills = _skills(profile)
        if skills:
            badges = " ".join(
                f'<span style="display:inline-block; padding:0.2rem 0.55rem; '
                f'margin:0 0.35rem 0.35rem 0; border-radius:999px; '
                f'background:#eef2ff; color:#3730a3; font-size:0.85rem;">'
                f"{escape(skill)}</span>"
                for skill in skills
            )
            st.markdown(badges, unsafe_allow_html=True)
        else:
            st.write(_EMPTY_VALUE)

        st.caption("경력 및 경험 요약")
        st.write(_value(profile, "experience_summary"))

        st.caption("선호 근무 환경")
        st.write(_value(profile, "preferred_environment"))

    with setting_col:
        st.subheader("코칭 설정")
        st.caption("AI 코칭 스타일")
        st.write(_value(profile, "assistant_style"))
        st.caption("일일 알림 시간")
        st.write(_value(profile, "daily_notification_time"))

        assessment_score = profile.get("assessment_score")
        assessment_level = _value(profile, "assessment_level")
        if assessment_score is not None or assessment_level != _EMPTY_VALUE:
            st.caption("역량 진단")
            if assessment_score is not None:
                st.metric("진단 점수", f"{assessment_score}점")
            st.write(f"등급: {assessment_level}")

    assessment_summary = profile.get("assessment_summary")
    if assessment_summary:
        with st.expander("역량 진단 상세 보기"):
            st.json(assessment_summary)
