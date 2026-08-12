import streamlit as st
from streamlit_session_browser_storage import SessionStorage

from core.auth_service import logout
from core.session_storage import is_logged_in
from core.styles import apply_admin_style


st.set_page_config(
    page_title="AI 취업 코치 관리자",
    page_icon="🛡️",
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

apply_admin_style()

start_page = st.Page(
    "app_pages/start.py",
    title="관리자 로그인",
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
    st.markdown('<div class="admin-brand">AI 취업 코치</div>', unsafe_allow_html=True)
    st.caption("ADMIN CONSOLE")
    
    if is_logged_in():        
        st.markdown('<span class="admin-status">관리자 로그인 중</span>', unsafe_allow_html=True)
        st.caption(st.session_state.get("user_id") or "인증된 관리자")
        st.divider()
        st.page_link(user_management_page, label="사용자 관리", icon="👥")
        st.page_link(loadmap_page, label="로드맵 관리", icon="🗺️")
        st.page_link(notice_page, label="공지사항 관리", icon="📢")
        st.divider()
        if st.button("로그아웃", use_container_width=True):
            logout()
            st.switch_page(start_page)
    else:
        st.caption("관리자 로그인이 필요합니다.")

navigation.run()
