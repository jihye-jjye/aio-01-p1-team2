from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

import pandas as pd
import streamlit as st

from clients.dashboard_client import get_dashboard_process
from core.api_client import BackendAPIError


def _number(section: Mapping[str, Any], key: str) -> int | float:
    return section.get(key, 0) or 0


def _date_time(value: Any) -> str:
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%Y.%m.%d %H:%M")
    except ValueError:
        return str(value)


st.title("대시보드")
st.caption("서비스 운영 현황을 기간별로 확인합니다.")

filter_col, refresh_col = st.columns([2, 5])
with filter_col:
    days = st.number_input("조회 기간 (일)", min_value=1, max_value=90, value=7, step=1)
with refresh_col:
    st.write("")
    st.caption(f"오늘을 기준으로 최근 {days}일을 집계합니다.")

try:
    response = get_dashboard_process(int(days))
except BackendAPIError as error:
    st.error(f"대시보드 정보를 불러오지 못했습니다: {error}")
    st.stop()

period = response.get("period", {})
users = response.get("users", {})
onboarding = response.get("onboarding", {})
assessment = response.get("assessment", {})
roadmaps = response.get("roadmaps", {})
quests = response.get("quests", {})

st.caption(f"집계 기간: {_date_time(period.get('start_at'))} ~ {_date_time(period.get('end_at'))}")

user_col, active_col, new_col, quest_col = st.columns(4)
user_col.metric("전체 사용자", f"{_number(users, 'total_users'):,}명")
active_col.metric("활성 계정", f"{_number(users, 'active_accounts'):,}명")
new_col.metric("기간 내 신규 가입", f"{_number(users, 'new_users'):,}명")
quest_col.metric("퀘스트 완료율", f"{_number(quests, 'completion_rate'):.2f}%")

left_col, right_col = st.columns([1, 1.5])
with left_col:
    with st.container(border=True):
        st.subheader("운영 현황")
        st.metric("온보딩 완료율", f"{_number(onboarding, 'completion_rate'):.2f}%", help="전체 사용자 대비 온보딩 완료 비율")
        st.progress(min(int(round(_number(onboarding, "completion_rate"))), 100))
        st.caption(f"완료 {_number(onboarding, 'completed_count'):,}명 · 미완료 {_number(onboarding, 'incomplete_count'):,}명")

        st.divider()
        st.write(f"진단 완료 사용자: **{_number(assessment, 'assessed_users'):,}명**")
        st.write(f"평균 진단 점수: **{_number(assessment, 'average_score'):.2f}점**")
        level_distribution = assessment.get("level_distribution", {})
        st.caption(
            "초급 {beginner}명 · 중급 {intermediate}명 · 고급 {advanced}명".format(
                beginner=_number(level_distribution, "beginner"),
                intermediate=_number(level_distribution, "intermediate"),
                advanced=_number(level_distribution, "advanced"),
            )
        )

with right_col:
    with st.container(border=True):
        st.subheader(f"가입자 추이 (최근 {days}일)")
        signup_data = response.get("daily_signups", [])
        if signup_data:
            chart_data = pd.DataFrame(signup_data)
            chart_data["date"] = pd.to_datetime(chart_data["date"])
            st.line_chart(chart_data.set_index("date")["count"], height=260)
        else:
            st.info("표시할 가입자 추이 데이터가 없습니다.")

st.subheader("로드맵 및 퀘스트")
roadmap_col, quest_col, today_col = st.columns(3)
with roadmap_col:
    with st.container(border=True):
        st.metric("활성 로드맵", f"{_number(roadmaps, 'active_plans'):,}개")
        st.caption(f"완료 {_number(roadmaps, 'completed_plans'):,}개 · 만료 {_number(roadmaps, 'expired_plans'):,}개")
with quest_col:
    with st.container(border=True):
        st.metric("전체 퀘스트", f"{_number(quests, 'total'):,}개")
        st.caption(f"완료 {_number(quests, 'completed'):,}개 · 대기 {_number(quests, 'pending'):,}개")
with today_col:
    with st.container(border=True):
        st.metric("오늘 일정", f"{_number(quests, 'scheduled_today'):,}개")
        st.caption(f"지연 {_number(quests, 'overdue'):,}개 · 면접 {_number(quests, 'interviews_today'):,}개")

st.subheader("최근 가입 사용자")
recent_users = response.get("recent_users", [])
if recent_users:
    recent_table = pd.DataFrame(recent_users)
    recent_table = recent_table.rename(
        columns={
            "login_id": "아이디",
            "target_role": "목표 직무",
            "user_exp": "경험치",
            "onboarding_completed": "온보딩 완료",
            "is_active": "활성 상태",
            "created_at": "가입일",
        }
    )
    visible_columns = ["아이디", "목표 직무", "경험치", "온보딩 완료", "활성 상태", "가입일"]
    st.dataframe(recent_table[visible_columns], use_container_width=True, hide_index=True)
else:
    st.info("최근 가입한 사용자가 없습니다.")
