"""관리자 공지사항 조회 화면."""

import streamlit as st

from clients.notice_client import notice_all_process
from core.api_client import BackendAPIError
from core.auth import is_logged_in
from core.styles import page_header

if not is_logged_in():
    st.warning("관리자 로그인이 필요한 페이지입니다.")
    if st.button("관리자 로그인으로 이동", type="primary"):
        st.switch_page("app_pages/start.py")
    st.stop()

page_header(
    "NOTICE MANAGEMENT",
    "공지사항 관리",
    "서비스에 등록된 공지 내용을 확인하고 운영 상태를 점검하세요.",
)

try:
    with st.spinner("공지사항을 불러오고 있어요..."):
        response = notice_all_process()
    if isinstance(response, dict):
        notices = response.get("items") or response.get("notices") or []
    elif isinstance(response, list):
        notices = response
    else:
        notices = []
except BackendAPIError as error:
    st.error(f"공지사항을 불러오지 못했습니다. {error}")
    st.stop()

st.metric("등록된 공지", f"{len(notices)}개")
st.divider()

if not notices:
    with st.container(border=True):
        st.subheader("등록된 공지사항이 없습니다")
        st.caption("공지 작성 API가 연결되면 이곳에서 등록과 관리 기능을 제공할 수 있어요.")
else:
    for notice in notices:
        with st.container(border=True):
            st.subheader(str(notice.get("title") or "제목 없는 공지"))
            st.caption(str(notice.get("created_at") or notice.get("published_at") or ""))
            st.write(str(notice.get("content") or notice.get("message") or "내용 없음"))
