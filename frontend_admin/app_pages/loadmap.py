"""관리자 로드맵 조회 안내 화면."""

import streamlit as st

from core.auth import is_logged_in
from core.styles import page_header


if not is_logged_in():
    st.warning("관리자 로그인이 필요한 페이지입니다.")
    if st.button("관리자 로그인으로 이동", type="primary"):
        st.switch_page("app_pages/start.py")
    st.stop()

page_header(
    "ROADMAP MANAGEMENT",
    "로드맵 관리",
    "사용자별 로드맵과 진행 현황을 조회하는 관리자 영역입니다.",
)

with st.container(border=True):
    st.subheader("사용자를 먼저 선택해 주세요")
    st.caption("사용자 관리에서 계정을 선택하면 해당 사용자의 로드맵을 확인할 수 있어요.")
    if st.button("사용자 관리로 이동", type="primary"):
        st.switch_page("app_pages/user_management.py")
