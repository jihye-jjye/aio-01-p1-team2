import streamlit as st
from streamlit_session_browser_storage import SessionStorage

from core.auth import is_logged_in, logout

st.set_page_config(
    page_title="취업 관리 MAP 관리자",
    page_icon="📚",
    layout="wide",
)

storage = SessionStorage()
if st.session_state.get("access_token"):
    storage.setItem("login_id", st.session_state.get("user_id", ""), key="save_login_id")
    storage.setItem(
        "access_token",
        st.session_state.access_token,
        key="save_access_token",
    )

start_page = st.Page(
    "app_pages/start.py",
    title="대쉬",
    icon="🏠",
    default=True,
)

user_management_page = st.Page(
    "app_pages/user_management.py",
    title="사용자 관리",
    icon="🗃️",
)

dashboard_page = st.Page(
    "app_pages/dashboard.py",
    title="대시보드",
    icon="📊",
)

user_management_detail_page = st.Page(
    "app_pages/user_management_detail.py",
    title="사용자 관리 상세보기",
    icon="🗃️",
)

loadmap_page = st.Page(
    "app_pages/loadmap.py",
    title="로드맵 관리",
    icon="🧭",
)

notice_page = st.Page(
    "app_pages/notice.py",
    title="공지사항",
    icon="🪧",
)

notice_detail_page = st.Page(
    "app_pages/notice_detail.py",
    title="공지사항 상세보기",
    icon="🪧",
)

recruitment_notice_page = st.Page(
    "app_pages/recruitment_notice.py",
    title="채용공고 관리",
    icon="",
)

recruitment_notice_detail_page = st.Page(
    "app_pages/recruitment_notice_detail.py",
    title="채용공고 등록/편집",
    icon="",
)

navigation = st.navigation(
    [start_page, dashboard_page, user_management_page, user_management_detail_page, notice_page, loadmap_page, notice_detail_page,
     recruitment_notice_page,recruitment_notice_detail_page
     ],
    position="hidden",
)

with st.sidebar:
    st.title("취업관리 MAP")   
    
    if is_logged_in():        
        st.page_link(dashboard_page)
        st.page_link(user_management_page)
        st.page_link(loadmap_page)
        st.page_link(notice_page)
        st.page_link(recruitment_notice_page)
        if st.button("로그아웃") :
            logout()
            st.switch_page(start_page)
        
        st.divider()
    else:   
        st.text("로그인 하여 관리자 기능을 이용하세요.")

navigation.run()
