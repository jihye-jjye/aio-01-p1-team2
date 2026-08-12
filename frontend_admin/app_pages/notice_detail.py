"""관리자 공지사항 상세 화면."""

import streamlit as st

from clients.notice_client import notice_get_process
from core.api_client import BackendAPIError
from core.auth import is_logged_in
from core.styles import page_header


if not is_logged_in():
    st.warning("관리자 로그인이 필요한 페이지입니다.")
    if st.button("관리자 로그인으로 이동", type="primary"):
        st.switch_page("app_pages/start.py")
    st.stop()

if st.button("← 공지사항 목록"):
    st.switch_page("app_pages/notice.py")

page_header(
    "NOTICE DETAIL",
    "공지사항 상세",
    "선택한 공지의 등록 내용과 식별 정보를 확인하세요.",
)

notice_id = st.session_state.get("selected_item_notice_id")
if not notice_id:
    st.info("조회할 공지사항을 먼저 선택해 주세요.")
    if st.button("공지사항 목록 보기", type="primary"):
        st.switch_page("app_pages/notice.py")
    st.stop()

try:
    with st.spinner("공지사항을 불러오고 있어요..."):
        response = notice_get_process(notice_id)

    if response:
        with st.container(border=True):
            st.subheader(str(response.get("title") or "제목 없는 공지"))
            st.caption(f'공지 ID · {response.get("id") or notice_id}')
            st.divider()
            st.write(str(response.get("content") or response.get("message") or "내용 없음"))
    else:
        st.info("표시할 공지사항 내용이 없습니다.")
except BackendAPIError as error:
    st.error(f"공지사항을 불러오지 못했습니다. {error}")
