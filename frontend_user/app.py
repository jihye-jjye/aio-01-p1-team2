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
    sync_auth_to_browser,
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
    url_path="login",
)
signup_page = st.Page(
    "app_pages/signup.py",
    title="회원가입",
    icon="✨",
    url_path="signup",
)
onboarding_page = st.Page(
    "app_pages/onboarding.py",
    title="AI 프로필 분석",
    icon="💬",
    url_path="profile-analysis",
)
assistant_page = st.Page(
    "app_pages/assistant.py",
    title="AI 상담",
    icon="🤖",
    url_path="assistant",
)
profile_page = st.Page(
    "app_pages/profile.py",
    title="내 프로필",
    icon="👤",
    url_path="profile",
)
dashboard_page = st.Page(
    "app_pages/dashboard.py",
    title="대시보드",
    icon="🏠",
    url_path="dashboard",
)
account_settings_page = st.Page(
    "app_pages/account_settings.py",
    title="사용자 정보 수정",
    icon="⚙️",
    url_path="account-settings",
)
roadmap_page = st.Page(
    "app_pages/roadmap.py",
    title="취업 로드맵",
    icon="🗺️",
    url_path="roadmap",
)
today_quests_page = st.Page(
    "app_pages/today_quests.py",
    title="오늘 할 일",
    icon="✅",
    url_path="today-quests",
)
jobs_page = st.Page(
    "app_pages/jobs.py",
    title="추천 공고",
    icon="💼",
    url_path="jobs",
)

# 페이지 목록 화면 이동은 각 페이지의 버튼으로 처리
navigation = st.navigation(
    [
        home_page,
        login_page,
        signup_page,
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

# 현재 페이지가 보호 화면일 때만 브라우저의 인증 상태를 복원합니다.
# 로그인 화면에서는 저장 컴포넌트를 실행하지 않아 폼 제출을 방해하지 않습니다.
PUBLIC_PATHS = {"", "login", "signup"}
if navigation.url_path not in PUBLIC_PATHS:
    restore_auth_from_browser()
    sync_auth_to_browser()

# 로그인에 성공한 사용자에게만 왼쪽 사이드바를 보여 줍니다.
if is_logged_in():
    with st.sidebar:
        st.title("AI 취업 코치")
        st.success("로그인 중")

        st.divider()

        # 사용자 기능 페이지가 추가되면 이곳에 링크 등록
        st.page_link(dashboard_page, label="홈", icon="🏠")
        st.page_link(roadmap_page, label="로드맵", icon="🗺️")
        st.page_link(today_quests_page, label="오늘 할 일", icon="✅")
        st.page_link(jobs_page, label="추천 공고", icon="💼")
        st.page_link(assistant_page, label="AI 상담", icon="🤖")
        st.page_link(profile_page, label="취업 프로필", icon="👤")


        st.divider()
        if st.button("로그아웃", use_container_width=True):
            clear_auth_state()
            # 로그아웃 후에는 로그인 화면이 아니라 사용자·관리자 모드 선택 화면으로 이동합니다.
            st.switch_page("app_pages/home.py")

# 현재 선택된 페이지 파일을 실행합니다.
navigation.run()
