import streamlit as st

from core.auth_sample import is_logged_in


def show_log() -> None:
    st.subheader("로그 조회")

    if not is_logged_in():
        st.warning("로그인이 필요한 화면입니다.")
        return

    st.info("로그 목록이 표시될 자리입니다.")
