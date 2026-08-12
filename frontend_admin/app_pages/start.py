"""관리자 로그인 화면."""

import streamlit as st
from core.auth_service import login
from core.session_storage import is_logged_in

if is_logged_in():
    st.switch_page("app_pages/dashboard.py")
from core.styles import page_header


page_header(
    "ADMIN ACCESS",
    "관리자 로그인",
    "운영 계정으로 로그인해 사용자와 서비스 데이터를 확인하세요.",
)
if is_logged_in():
    st.success("관리자 계정으로 로그인되어 있습니다.")
    if st.button("대쉬보드로 이동", type="primary"):
        st.switch_page("app_pages/dashboard.py")
else:
    left_space, form_column, right_space = st.columns([1, 1.4, 1])
    with form_column:
        with st.container(border=True):
            st.subheader("계정 확인")
            st.caption("발급받은 관리자 아이디와 비밀번호를 입력해 주세요.")

            with st.form("admin_login_form"):
                admin_id = st.text_input(
                    "관리자 아이디",
                    placeholder="admin ID",
                    value="admin01"
                )
                password = st.text_input(
                    "비밀번호",
                    type="password",
                    placeholder="비밀번호를 입력하세요",
                    value="Ah159#h!"
                )
                submitted = st.form_submit_button(
                    "관리자 로그인",
                    type="primary",
                    use_container_width=True,
                )

            if submitted:
                if not admin_id.strip() or not password:
                    st.warning("아이디와 비밀번호를 모두 입력해 주세요.")
                else:
                    with st.spinner("관리자 계정을 확인하고 있어요..."):
                        response = login(admin_id.strip(), password)
                    if response and response.get("access_token"):
                        st.switch_page("app_pages/dashboard.py")
