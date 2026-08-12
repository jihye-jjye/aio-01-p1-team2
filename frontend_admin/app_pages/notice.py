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

import streamlit as st
from clients.notice_client import notice_all_process
from core.api_client import BackendAPIError

try:
    response = notice_all_process()
    if response is not None:
        with st.container(border=True):
            # ID / 이름 / 아이디 / 역할 / 레벨 / 상태 / 가입일 / 관리
            column_widths = [2.0, 1.0, 1.2, 1.2, 1.8]

            # 헤더
            header_cols = st.columns(column_widths)
            headers = ["ID", "제목", "가입일", "수정일", "관리"]

            for col, header in zip(header_cols, headers):
                col.markdown(f'<div class="table-head">{header}</div>', unsafe_allow_html=True)

            st.divider()

            # 행
            for item in response["items"]:
                row_cols = st.columns(column_widths)
                row_cols[0].write(item["id"])
                row_cols[1].write(item["title"])
                # row_cols[2].write(item["content"])      
                row_cols[2].write(item["created_at"])
                row_cols[3].write(item["updated_at"] if item["updated_at"] is not None else "")

                # 마지막 '관리' 컬럼
                with row_cols[4]:
                    edit_col, delete_col = st.columns(2)

                    with edit_col:
                        if st.button(
                            "수정",
                            key=f"user-edit-{item['id']}",
                            use_container_width=True):                    
                            st.session_state.selected_item_notice_id = item["id"]
                            # 여기서 수정 페이지 또는 수정 폼을 열기
                            st.switch_page("app_pages/notice_detail.py")

                    with delete_col:
                        if st.button(
                            "삭제",
                            key=f"user-delete-{item['id']}",
                            use_container_width=True,
                        ):
                            st.session_state.delete_notice_id = item["id"]
                            # 여기서 삭제 확인창 또는 삭제 API 호출

                st.divider()
except BackendAPIError as error:
    st.warning(str(error))
