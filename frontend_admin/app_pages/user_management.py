import streamlit as st
import pandas as pd

from core.api_client import BackendAPIError
from clients.user_client import user_get_all_process

st.markdown(
    '<div class="breadcrumb">대시보드 〉 사용자 관리</div>',
    unsafe_allow_html=True
)

st.subheader("사용자 관리", divider="rainbow")

# ---------------------------------------------------------
# Search / Filter Area
# ---------------------------------------------------------
search_col, role_col, status_col, button_col = st.columns(
    [4, 1.5, 1.5, 1.3]
)

with search_col:
    keyword = st.text_input(
        "사용자 검색",
        placeholder="사용자 검색 (이름, ID)",
        label_visibility="collapsed"
    )

with role_col:
    selected_role = st.selectbox(
        "역할",
        ["전체 역할", "일반", "관리자"],
        label_visibility="collapsed"
    )

with status_col:
    selected_status = st.selectbox(
        "상태",
        ["전체 상태", "활성", "비활성"],
        label_visibility="collapsed"
    )

with button_col:
    add_user = st.button(
        "＋ 사용자 추가",
        type="primary",
        use_container_width=True
    )

user_infos = user_get_all_process()

items = user_infos or []
with st.container(border=True):
    # ID / 이름 / 아이디 / 역할 / 레벨 / 상태 / 가입일 / 관리
    column_widths = [2.0, 1.0, 0.5, 0.8, 0.8, 1.2, 1.2, 1.8]

    # 헤더
    header_cols = st.columns(column_widths)
    headers = ["ID", "사용자 아이디", "역할", "경험치", "상태", "가입일", "마지막 접속일", "관리"]

    for col, header in zip(header_cols, headers):
        col.markdown(f"**{header}**")

    st.divider()

    # 행
    for item in user_infos["items"]:
        row_cols = st.columns(column_widths)

        if(item["role"] == "user"):
            row_cols[0].write(item["id"])
            row_cols[1].write(item["login_id"])
            row_cols[2].write(item["role"])
            row_cols[3].write(item["user_exp"])
            row_cols[4].write("활성화" if item["is_active"] else "비활성화")
            row_cols[5].write(item["created_at"])
            row_cols[6].write(item["last_login_at"] if item["last_login_at"] is not None else "")

            # 마지막 '관리' 컬럼
            with row_cols[7]:
                edit_col, delete_col = st.columns(2)

                with edit_col:
                    if st.button(
                        "수정",
                        key=f"user-edit-{item['id']}",
                        use_container_width=True):                    
                        st.session_state.selected_item_login_id = item["login_id"]
                        # 여기서 수정 페이지 또는 수정 폼을 열기
                        st.switch_page("app_pages/user_management_detail.py")

                with delete_col:
                    if st.button(
                        "삭제",
                        key=f"user-delete-{item['id']}",
                        use_container_width=True,
                    ):
                        st.session_state.delete_item_id = item["id"]
                        # 여기서 삭제 확인창 또는 삭제 API 호출

            st.divider()