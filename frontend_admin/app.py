import streamlit as st

from core.auth import init_state, is_logged_in, logout


st.set_page_config(
    page_title="취업 관리 MAP 관리자",
    page_icon="📚",
    layout="wide",
)

init_state()

start_page = st.Page(
    "app_pages/start.py",
    icon="🏠",
    default=True,
)

dash_home_page = st.Page(
    "app_pages/user_management.py",
    title="대시",
    icon="🗃️",
)

select_page = st.Page(
    "app_pages/example.py",
    title="조회",
    icon="🔍",
)

chatbot_page = st.Page(
    "app_pages/chat_example.py",
    title="Chat",
    icon="🤖",
)

navigation = st.navigation(
    [start_page, dash_home_page, select_page, chatbot_page],
    position="hidden",
)

with st.sidebar:
    st.title("취업관리 MAP")       

    if is_logged_in():        
        st.page_link(dash_home_page)
        st.page_link(select_page)
        st.page_link(chatbot_page)
        if st.button("로그아웃") :
            logout()
            st.switch_page(start_page)
        
        st.divider()
    else:
        # st.page_link(start_page)    
        st.text("로그인 하여 관리자 기능을 이용하세요.")

navigation.run()
