#사용자 회원가입

import re

import streamlit as st

from clients.auth_client import signup
from core.api_client import BackendAPIError
from core.session import save_auth_tokens


LOGIN_ID_PATTERN = re.compile(r"^[a-z0-9._-]{4,50}$")
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128

def apply_signup_style() -> None:
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"],
        button[data-testid="stBaseButton-headerNoPadding"],
        [data-testid="collapsedControl"] {
            display: none !important;
        }
        .stApp {
            background: #ffffff;
            color: #111827;
        }

        .stApp h1, .stApp h2, .stApp h3,
        .stApp p, .stApp label,
        .stApp [data-testid="stCaptionContainer"],
        .stApp [data-testid="stMarkdownContainer"] {
            color: #111827;
        }

        div[data-testid="stTextInput"] label,
        div[data-testid="stTextInput"] label p {
            color: #111827 !important;
            font-weight: 600;
        }

        div[data-testid="stTextInput"] input {
            background: #ffffff;
            color: #111827;
            border: 1px solid #d1d5db;
        }

        div[data-testid="stTextInput"] input::placeholder {
            color: #6b7280;
            opacity: 1;
        }

        div[data-testid="stTextInput"] input:focus {
            border-color: #2563eb;
            box-shadow: 0 0 0 1px #2563eb;
        }

        div[data-testid="stForm"] {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 24px;
        }

        div[data-testid="stFormSubmitButton"] button {
            background: #2563eb;
            color: #ffffff;
            border: 1px solid #2563eb;
        }

        div[data-testid="stFormSubmitButton"] button p {
            color: #ffffff !important;
        }

        div[data-testid="stButton"] button {
            background: #ffffff;
            color: #111827;
            border: 1px solid #d1d5db;
        }

        div[data-testid="stButton"] button p {
            color: #111827 !important;
        }

        /* Streamlit 탭을 추가해도 흰 배경과 검정 글씨를 유지합니다. */
        div[data-baseweb="tab-list"] {
            background: #ffffff;
        }

        button[data-baseweb="tab"] p {
            color: #111827 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def validate_signup(
    user_name: str,
    login_id: str,
    login_pw: str,
    password_confirm: str,
) -> list[str]:
    """회원가입 입력값의 문제를 찾아 사용자에게 보여 줄 문장 목록을 만듭니다."""

    errors: list[str] = []
    normalized_id = login_id.strip().casefold()

    if not normalized_id:
        errors.append("아이디를 입력해 주세요.")
    elif not LOGIN_ID_PATTERN.fullmatch(normalized_id):
        errors.append(
            "아이디는 4자 이상의 영문 소문자, 숫자, "
            "점(.), 밑줄(_), 하이픈(-)만 사용할 수 있습니다."
        )

    if not login_pw:
        errors.append("비밀번호를 입력해 주세요.")
    elif not MIN_PASSWORD_LENGTH <= len(login_pw) <= MAX_PASSWORD_LENGTH:
        errors.append(
            f"비밀번호는 {MIN_PASSWORD_LENGTH}~"
            f"{MAX_PASSWORD_LENGTH}자로 입력해 주세요."
        )

    if not password_confirm:
        errors.append("비밀번호 확인을 입력해 주세요.")
    elif login_pw != password_confirm:
        errors.append("비밀번호가 일치하지 않습니다.")

    if not user_name.strip():
        errors.append("사용자 이름을 입력해 주세요.")

    return errors


def handle_signup(
    user_name: str,
    login_id: str,
    login_pw: str,
    password_confirm: str,
    message_area,
) -> None:
    """검증을 통과한 값을 백엔드에 보내고 AI 프로필 분석으로 이동합니다."""

    errors = validate_signup(
        user_name,
        login_id,
        login_pw,
        password_confirm,

    )

    if errors:
        with message_area.container():
            for error in errors:
                st.warning(error)
        return

    try:
        # 아이디는 auth_client에서 trim/casefold 처리됩니다.
        # 비밀번호는 공백 제거 없이 그대로 전송됩니다.
        # 회원가입 성공 응답에도 로그인 토큰이 포함됩니다.
        signup_result = signup(
            user_name=user_name,
            login_id=login_id,
            login_pw=login_pw,
        )
        save_auth_tokens(signup_result)

        # 회원가입 화면에서 받은 이름은 GET /auth/me가 이름을 제공하기 전까지
        # 대시보드 인사말에 사용할 수 있도록 인증 세션에 함께 저장합니다.
        st.session_state.user = {
            "id": str(signup_result.get("user_id") or ""),
            "login_id": str(signup_result.get("login_id") or login_id),
            "user_name": user_name.strip(),
            "role": "user",
        }
    except BackendAPIError as error:
        show_signup_error(error, message_area)
        return

    # 회원가입 응답으로 받은 토큰을 유지하고 AI 프로필 분석을 바로 시작합니다.
    # 다음 페이지에서 한 번만 보여 줄 안내 문구입니다.
    st.session_state.onboarding_flash = (
        "회원가입이 완료되었습니다. 취업 프로필 작성을 시작합니다."
    )
    st.switch_page("app_pages/onboarding.py")


def show_signup_error(error: BackendAPIError, message_area) -> None:
    """백엔드 error.code에 맞는 사용자 안내 문구를 표시합니다."""

    if error.code == "LOGIN_ID_ALREADY_EXISTS":
        message_area.error(
            "이미 가입된 아이디입니다. 기존 계정으로 로그인해 주세요."
        )

    elif error.code == "VALIDATION_ERROR":
        message_area.error("입력한 아이디와 비밀번호를 확인해 주세요.")

    elif error.code in {
        "SERVICE_UNAVAILABLE",
        "CLIENT_TIMEOUT",
        "NETWORK_ERROR",
    }:
        message_area.warning(
            "계정이 이미 생성됐을 수 있습니다. "
            "회원가입을 반복하지 말고 같은 정보로 로그인해 주세요."
        )

    else:
        message_area.error(error.message)


def render_signup_form() -> None:
    """회원가입 입력 폼과 로그인 이동 버튼을 표시합니다."""

    apply_signup_style()
    # 성공·경고·오류 메시지는 항상 페이지 내용 최상단에 표시합니다.
    message_area = st.empty()
    left_space, form_column, right_space = st.columns(
        [1, 1.4, 1]
    )

    with form_column:
        st.title("회원가입")
        st.caption(
            "계정 정보를 입력해 주세요."
        )

        with st.form(
            "signup_form",
            clear_on_submit=False,
        ):
            user_name = st.text_input(
                "사용자 이름",
                placeholder="이름을 입력하세요",
            )

            login_id = st.text_input(
                "아이디",
                placeholder="예: user",
                help=(
                    "4자 이상의 영문 소문자, 숫자, "
                    "점, 밑줄, 하이픈을 사용할 수 있습니다."
                ),
            )

            login_pw = st.text_input(
                "비밀번호",
                type="password",
                placeholder=f"{MIN_PASSWORD_LENGTH}자 이상 입력",
                help="비밀번호에 입력한 공백도 비밀번호에 포함됩니다.",
            )

            password_confirm = st.text_input(
                "비밀번호 확인",
                type="password",
                placeholder="비밀번호를 다시 입력하세요",
            )

            submitted = st.form_submit_button(
                "회원가입",
                use_container_width=True,
                type="primary",
            )

        st.caption("이미 계정이 있으신가요?")

        if st.button(
            "로그인으로 이동",
            use_container_width=True,
        ):
            st.switch_page("app_pages/login.py")

    if submitted:
        handle_signup(
            user_name,
            login_id,
            login_pw,
            password_confirm,
            message_area,
        )


def main() -> None:
    render_signup_form()


main()
