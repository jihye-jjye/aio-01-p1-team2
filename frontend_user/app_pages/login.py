#login.py 사용자 로그인 화면

import streamlit as st

from clients.auth_client import get_me, get_profile, login
from core.api_client import BackendAPIError
from core.session import persist_auth_state, save_auth_tokens


def initialize_login_state() -> None:
    """로그인 화면에서 처음 사용할 session_state 기본값을 만듭니다."""

    defaults = {
        "user_name": "",
        "logged_in": False,
        "user_id": "",
        "remember_login": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def apply_login_style() -> None:
    """로그인 페이지에만 적용할 색상과 배치 CSS입니다."""

    st.markdown(
        """
        <style>
        #MainMenu, footer, header { visibility: hidden; }
        .stApp {
            background: linear-gradient(rgba(8,11,22,.96), rgba(8,11,22,.96));
            color: #e8e8f0;
        }
        .stApp h1, .stApp h2, .stApp h3, .stApp p,
        .stApp label, .stApp [data-testid="stCaptionContainer"],
        .stApp [data-testid="stMarkdownContainer"] {
            color: #f5f5f7;
        }
        .block-container { max-width: 980px; padding-top: 3rem; }
        .window-header {
            display:flex; justify-content:space-between; align-items:center;
            padding:16px 22px; color:#ef75cf; border:1px solid #5b315e;
            border-radius:7px 7px 0 0; font-family:monospace; font-weight:700;
        }
        .login-title { margin:28px 0 8px; color:#8fe35c; font-size:24px; font-weight:800; }
        .login-description { color:#9295a7; margin-bottom:22px; }
        .speech-bubble {
            border:1px solid #30364c; background:#101521; border-radius:9px;
            padding:18px; color:#d6d8e4; line-height:1.6; margin-top:35px;
        }
        .character { text-align:center; font-size:100px; margin-top:25px; }
        .system-status {
            border-top:1px solid #25283a; margin-top:38px; padding:20px 22px;
            color:#69d76f; font-family:monospace; font-size:13px; line-height:1.8;
        }
        div[data-testid="stTextInput"] input {
            background:#0f1220; color:#f1f1f7; border:1px solid #34354d;
        }
        div[data-testid="stTextInput"] input::placeholder {
            color:#8f91a2;
            opacity:1;
        }
        div[data-testid="stCheckbox"] label,
        div[data-testid="stCheckbox"] label p {
            color:#f5f5f7 !important;
        }
        div[data-testid="stFormSubmitButton"] button {
            height:52px; color:#ff78c5; background:#240b24;
            border:2px solid #e43b99; font-weight:800; font-size:18px;
        }
        div[data-testid="stPageLink"] {
            margin-top:16px;
            text-align:center;
        }
        div[data-testid="stPageLink"] a {
            justify-content:center;
            color:#ff78c5 !important;
            text-decoration:none;
        }
        div[data-testid="stPageLink"] a:hover {
            color:#ffffff !important;
            text-decoration:underline;
        }
        a[data-testid="stPageLink-NavLink"] p {
            color:#f5f5f7 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def submit_login(user_id: str, password: str, remember: bool, message_area) -> None:
    """입력값을 검사하고 로그인 API 결과에 따라 다음 화면으로 이동합니다."""

    # 빈 값은 백엔드까지 보내지 않고 프론트에서 먼저 안내합니다.
    if not user_id.strip():
        message_area.error("아이디를 입력해 주세요.")
        return
    if not password:
        message_area.error("비밀번호를 입력해 주세요.")
        return

    try:
        # client는 요청만 담당하고, 받은 토큰은 session 모듈로 저장합니다.
        login_result = login(user_id, password)
        save_auth_tokens(login_result, remember=remember)
        st.session_state.user = get_me()
        # 프로필이 없으면 신규 사용자이므로 AI 프로필 분석을 시작합니다.
        try:
            st.session_state.profile = get_profile()
            st.session_state.next_screen = "main"
        except BackendAPIError as error:
            if error.code == "PROFILE_NOT_FOUND":
                st.session_state.next_screen = "onboarding"
            else:
                raise
        # 사용자와 프로필 조회 결과까지 새로고침 후 복원할 수 있도록 갱신합니다.
        persist_auth_state()
    except BackendAPIError as error:
        if error.code == "INVALID_CREDENTIALS":
            message_area.error("아이디 또는 비밀번호가 올바르지 않습니다.")
        elif error.code in {"CLIENT_TIMEOUT", "NETWORK_ERROR"}:
            message_area.error("서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.")
        else:
            message_area.error(error.message)
        return

    st.session_state.remember_login = remember
    if st.session_state.next_screen == "onboarding":
        st.switch_page("app_pages/onboarding.py")
    else:
        st.switch_page("app_pages/dashboard.py")


def show_login_page() -> None:
    """로그인 화면 전체를 위에서 아래 순서로 그립니다."""

    initialize_login_state()
    apply_login_style()
    # 성공·경고·오류 메시지는 항상 페이지 내용 최상단에 표시합니다.
    message_area = st.empty()
    flash_message = st.session_state.pop("auth_flash", None)
    if flash_message:
        message_area.success(flash_message)

    st.markdown(
        '<div class="window-header"><span>❯ 01 로그인</span><span>— □ ×</span></div>',
        unsafe_allow_html=True,
    )
    _, form_column, character_column, _ = st.columns([0.25, 1.2, 0.9, 0.25])

    with form_column:
        st.markdown(
            """
            <div class="login-title">내 커리어 퀘스트, 이어서 시작!</div>
            <div class="login-description">로그인하고 오늘의 미션부터 가볍게 클리어해 보세요.</div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("login_form"):
            user_id = st.text_input("아이디", placeholder="user")
            password = st.text_input("비밀번호", type="password", placeholder="비밀번호를 입력하세요")
            submitted = st.form_submit_button("❯ 로그인", use_container_width=True)
        if submitted:
            submit_login(user_id, password, False, message_area)
        st.page_link(
            "app_pages/signup.py",
            label="계정이 없으신가요? 회원가입",
            icon="✨",
        )

    with character_column:
        st.markdown(
            """
            <div class="speech-bubble">환영해요!<br>당신의 취업 성공을 위해<br>저희가 함께할게요!</div>
            <div class="character">🧑🏻‍💻</div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="system-status">❯ CONNECTED TO JOB QUEST<br>❯ AI ASSISTANT READY</div>',
        unsafe_allow_html=True,
    )


show_login_page()
