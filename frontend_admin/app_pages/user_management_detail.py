
"""관리자 사용자 상세 화면."""

import streamlit as st
from pathlib import Path

from clients.user_client import user_get_overview_process
from core.api_client import BackendAPIError
from core.session_storage import is_logged_in
from core.datetime_format import format_created_at
from core.styles import page_header

PROFILE_FIELDS = {
    "target_role": "목표 직무",
    "skills": "보유 기술",
    "experience_summary": "경험 요약",
    "target_date": "목표 취업일",
    "target_company": "희망 기업",
    "preferred_environment": "선호 근무 환경",
}
CHARACTER_IMAGE = Path(__file__).resolve().parents[1] / "resources" / "캐릭터.png"


def display_value(value: object) -> str:
    """프로필 값을 관리자 화면용 문자열로 변환합니다."""

    if isinstance(value, list):
        return ", ".join(map(str, value)) if value else "-"
    return str(value) if value not in (None, "") else "-"


if not is_logged_in():
    st.warning("관리자 로그인이 필요한 페이지입니다.")
    if st.button("관리자 로그인으로 이동", type="primary"):
        st.switch_page("app_pages/start.py")
    st.stop()

if st.button("← 사용자 목록"):
    st.switch_page("app_pages/user_management.py")

login_id = st.session_state.get("selected_item_login_id")
if not login_id:
    st.info("조회할 사용자를 먼저 선택해 주세요.")
    if st.button("사용자 선택하기", type="primary"):
        st.switch_page("app_pages/user_management.py")
    st.stop()

try:
    with st.spinner("사용자 상세 정보를 불러오고 있어요..."):
        response = user_get_overview_process(str(login_id)) or {}
except BackendAPIError as error:
    st.error(f"사용자 상세 정보를 불러오지 못했습니다. {error}")
    st.stop()

account = response.get("account") or {}
profile = account.get("profile") or response.get("profile") or {}
quests = response.get("quests") or []
quest_progress = response.get("quest_progress") or {}

page_header(
    "USER DETAIL",
    str(account.get("login_id") or login_id),
    "계정 상태와 취업 프로필, 퀘스트 진행 현황을 확인하세요.",
)

with st.container(border=True):
    avatar_column, identity_column, status_column = st.columns([.7, 3, 1.2])
    with avatar_column:
        if CHARACTER_IMAGE.exists():
            st.image(str(CHARACTER_IMAGE), width=84)
        else:
            st.markdown("## 👤")
    with identity_column:
        st.subheader(str(account.get("login_id") or login_id))
        st.caption(str(account.get("id") or "사용자 UUID 없음"))
    with status_column:
        st.write("🟢 활성 계정" if account.get("is_active") else "⚪ 비활성 계정")
        st.caption("사용자" if account.get("role") == "user" else "관리자")

metric_columns = st.columns(4)
metric_columns[0].metric("누적 EXP", int(account.get("user_exp") or 0))
metric_columns[1].metric("계정 역할", "사용자" if account.get("role") == "user" else "관리자")
metric_columns[2].metric("가입일", format_created_at(account.get("created_at")))
metric_columns[3].metric("최근 접속", format_created_at(account.get("last_login_at")))

profile_tab, quest_tab, access_tab = st.tabs(["취업 프로필", "퀘스트 진행", "계정 정보"])

with profile_tab:
    if not profile:
        st.info("아직 완성된 취업 프로필이 없습니다.")
    else:
        fields = list(PROFILE_FIELDS.items())
        for index in range(0, len(fields), 2):
            columns = st.columns(2)
            for column, (field, label) in zip(columns, fields[index:index + 2]):
                with column:
                    with st.container(border=True):
                        st.caption(label)
                        st.write(f'**{display_value(profile.get(field))}**')

with quest_tab:
    progress_columns = st.columns(4)
    progress_columns[0].metric("전체", int(quest_progress.get("total") or 0))
    progress_columns[1].metric("완료", int(quest_progress.get("completed") or 0))
    progress_columns[2].metric("진행 중", int(quest_progress.get("in_progress") or 0))
    progress_columns[3].metric("대기", int(quest_progress.get("pending") or 0))
    progress_percent = max(0, min(100, int(quest_progress.get("progress_percent") or 0)))
    st.progress(progress_percent / 100)
    st.caption(f"전체 퀘스트 진행률 {progress_percent}%")

    quest_items = quests.get("items") if isinstance(quests, dict) else quests
    quest_items = quest_items or []
    if not quest_items:
        st.info("표시할 퀘스트 기록이 없습니다.")
    else:
        st.dataframe(quest_items, use_container_width=True, hide_index=True)

with access_tab:
    with st.container(border=True):
        st.write(f'**계정 상태** · {"활성" if account.get("is_active") else "비활성"}')
        st.write(f'**가입일** · {format_created_at(account.get("created_at"))}')
        st.write(f'**마지막 접속** · {format_created_at(account.get("last_login_at"))}')
