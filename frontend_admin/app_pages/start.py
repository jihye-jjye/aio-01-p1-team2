import streamlit as st

from core.auth_service import login
from core.session_storage import is_logged_in

if is_logged_in():
    st.switch_page("app_pages/dashboard.py")

st.subheader("관리자 로그인")

with st.form("signup_form"):
    admin_id = st.text_input("아이디", value="admin01")
    password = st.text_input("패스워드", type="password", value="Ah159#h!")
    # login_autho = st.checkbox("로그인 상태 유지")
    submitted = st.form_submit_button("로그인", use_container_width=True, type="primary", )

    if submitted:
        if admin_id and password:
            response = login(admin_id, password)
            if response and response.get("access_token"):
                st.switch_page("app_pages/dashboard.py")
            else:
                st.error("로그인에 실패했습니다.")            
        else:
            st.warning("모든 항목을 입력해 주세요.")
