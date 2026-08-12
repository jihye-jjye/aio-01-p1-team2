import re

import streamlit as st

from frontend_user.clients.auth_client import get_profile, signup
from frontend_user.core.api_client import BackendAPIError


LOGIN_ID_PATTERN = re.compile(r"^[a-z0-9._-]{4,50}$")


def _submit_signup(login_id: str, login_pw: str, user_name: str) -> None:
    normalized_id = login_id.strip().casefold()
    if not LOGIN_ID_PATTERN.fullmatch(normalized_id):
        st.error("아이디는 4자 이상의 영문 소문자, 숫자, 점, 밑줄, 하이픈만 사용할 수 있습니다.")
        return
    if not 8 <= len(login_pw) <= 128:
        st.error("비밀번호는 8자 이상 입력해 주세요.")
        return
    if not user_name.strip():
        st.error("사용자 이름을 입력해 주세요.")
        return

    try:
        signup(normalized_id, login_pw, user_name)
        try:
            st.session_state.profile = get_profile()
            st.session_state.next_screen = "main"
        except BackendAPIError as error:
            if error.code == "PROFILE_NOT_FOUND":
                st.session_state.next_screen = "onboarding"
            else:
                raise
    except BackendAPIError as error:
        if error.code == "LOGIN_ID_ALREADY_EXISTS":
            st.error("이미 가입된 아이디입니다. 로그인해 주세요.")
        elif error.code == "VALIDATION_ERROR":
            st.error("아이디와 비밀번호 입력값을 확인해 주세요.")
        elif error.code in {
            "SERVICE_UNAVAILABLE",
            "CLIENT_TIMEOUT",
            "NETWORK_ERROR",
        }:
            st.warning(
                "계정이 생성됐을 수 있습니다. 회원가입을 반복하지 말고 "
                "같은 정보로 로그인해 주세요."
            )
        else:
            st.error(error.message)
        return

    st.success("회원가입이 완료되었습니다.")


def show_signup() -> None:
    st.subheader("회원가입")

    with st.form("signup_form"):
        login_id = st.text_input("아이디", key="signup_id")
        login_pw = st.text_input(
            "비밀번호",
            type="password",
            key="signup_password",
        )
        user_name = st.text_input("사용자 이름", key="signup_user_name")
        submitted = st.form_submit_button("회원가입")

    if submitted:
        _submit_signup(login_id, login_pw, user_name)
