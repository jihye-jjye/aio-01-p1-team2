import streamlit as st


def show_signup() -> None:
    st.subheader("회원가입")

    with st.form("signup_form"):
        user_id = st.text_input("아이디", key="signup_id")
        password = st.text_input(
            "비밀번호",
            type="password",
            key="signup_password",
        )
        name = st.text_input("이름")
        submitted = st.form_submit_button("회원가입")

    if submitted:
        if user_id and password and name:
            st.success(f"{name}님의 회원 정보가 입력되었습니다.")
        else:
            st.warning("모든 항목을 입력해 주세요.")
