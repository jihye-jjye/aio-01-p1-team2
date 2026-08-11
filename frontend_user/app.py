import sys
from pathlib import Path

import streamlit as st


# 어느 폴더에서 실행해도 core, clients 모듈을 찾도록 앱 폴더를 등록합니다.
FRONTEND_ROOT = Path(__file__).resolve().parent
if str(FRONTEND_ROOT) not in sys.path:
    sys.path.insert(0, str(FRONTEND_ROOT))

from core.session import (
    clear_auth_state,
    is_logged_in,
    restore_auth_from_browser,
)
from core.styles import apply_global_button_style


# 브라우저 탭 제목, 아이콘, 화면 너비를 앱 전체에서 한 번 설정합니다.
st.set_page_config(
    page_title="AI 취업 코치",
    page_icon="🤖",
    layout="wide",
)

# 모든 페이지에서 같은 버튼 색상을 사용합니다.
apply_global_button_style()

# 브라우저 새로고침으로 Streamlit 세션이 새로 만들어져도 로그인을 복원합니다.
restore_auth_from_browser()

# st.Page는 실제 화면 파일을 앱의 한 페이지로 등록하는 기능입니다.
# position="hidden"을 사용하므로 로그인 전에는 기본 페이지 메뉴가 보이지 않습니다.
home_page = st.Page(
    "app_pages/home.py",
    title="모드 변경",
    icon="🏠",
    default=True,
)
login_page = st.Page(
    "app_pages/login.py",
    title="로그인",
    icon="🔐",
)
signup_page = st.Page(
    "app_pages/signup.py",
    title="회원가입",
    icon="✨",
)
admin_login_page = st.Page(
    "app_pages/admin_login.py",
    title="관리자 로그인",
    icon="🛡️",
)
onboarding_page = st.Page(
    "app_pages/onboarding.py",
    title="AI 프로필 분석",
    icon="💬",
)
assistant_page = st.Page(
    "app_pages/assistant.py",
    title="AI 상담",
    icon="🤖",
)
profile_page = st.Page(
    "app_pages/profile.py",
    title="내 프로필",
    icon="👤",
)
dashboard_page = st.Page(
    "app_pages/dashboard.py",
    title="대시보드",
    icon="🏠",
)
account_settings_page = st.Page(
    "app_pages/account_settings.py",
    title="사용자 정보 수정",
    icon="⚙️",
)
roadmap_page = st.Page(
    "app_pages/roadmap.py",
    title="취업 로드맵",
    icon="🗺️",
)
today_quests_page = st.Page(
    "app_pages/today_quests.py",
    title="오늘 할 일",
    icon="✅",
)
jobs_page = st.Page(
    "app_pages/jobs.py",
    title="추천 공고",
    icon="💼",
)

# 페이지 목록 화면 이동은 각 페이지의 버튼으로 처리
navigation = st.navigation(
    [
        home_page,
        login_page,
        signup_page,
        admin_login_page,
        onboarding_page,
        assistant_page,
        profile_page,
        dashboard_page,
        account_settings_page,
        roadmap_page,
        today_quests_page,
        jobs_page,
    ],
    position="hidden",
)

# 로그인에 성공한 사용자에게만 왼쪽 사이드바를 보여 줍니다.
if is_logged_in():
    with st.sidebar:
        st.title("AI 취업 코치")
        user = st.session_state.get("user") or {}
        st.success("로그인 중")
        st.caption(user.get("login_id", "인증된 사용자"))
        st.divider()

        # 사용자 기능 페이지가 추가되면 이곳에 링크 등록
        st.page_link(dashboard_page, label="홈", icon="🏠")
        st.page_link(profile_page, label="취업 프로필", icon="👤")
        st.page_link(roadmap_page, label="취업 로드맵", icon="🗺️")
        st.page_link(today_quests_page, label="오늘 할 일", icon="✅")
        st.page_link(jobs_page, label="추천 공고", icon="💼")
        st.page_link(assistant_page, label="AI 상담", icon="🤖")

        st.divider()
        if st.button("로그아웃", use_container_width=True):
            clear_auth_state()
            st.switch_page("app_pages/home.py")

# 현재 선택된 페이지 파일을 실행합니다.
navigation.run()
