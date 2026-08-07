import streamlit as st

from frontend_user.core.auth_sample import init_state, is_logged_in, login, logout


st.set_page_config(
    page_title="Multi Tab",
    page_icon="📚",
    layout="wide",
)

init_state()

start_page = st.Page(
    "app_pages/01_start.py",
    title="시작",
    icon="🏠",
    default=True,
)
data_page = st.Page(
    "app_pages/03_data.py",
    title="데이터",
    icon="📊",
)

select_page = st.Page(
    "app_pages/05_select.py",
    title="조회",
    icon="🔍",
)

chatbot_page = st.Page(
    "app_pages/07_chat.py",
    title="Chat",
    icon="🤖",
)

navigation = st.navigation(
    [start_page, data_page, select_page, chatbot_page],
    position="hidden",
)

with st.sidebar:
    st.title("Multi Tab")
    st.page_link(start_page)
    st.page_link(data_page)
    st.page_link(select_page)
    st.divider()

    if is_logged_in():
        st.success("로그인 중")
        st.write(f"사용자 ID : {st.session_state.user_id}")
        st.page_link(chatbot_page)
        st.button("로그아웃", on_click=logout)
    else:
        st.caption("연습 계정: id01 / pwd01")

        with st.form("sidebar_login_form"):
            user_id = st.text_input("아이디", value="id01")
            password = st.text_input("비밀번호", type="password", value="pwd01")
            submitted = st.form_submit_button(
                "로그인",
                use_container_width=True,
            )

        if submitted:
            if login(user_id, password):
                st.rerun()
            else:
                st.error("로그인 정보가 올바르지 않습니다.")

navigation.run()
