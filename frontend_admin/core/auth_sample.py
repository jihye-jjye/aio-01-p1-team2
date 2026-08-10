import streamlit as st


def init_state() -> None:
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        # st.session_state.logged_in = True
    if "user_id" not in st.session_state:
        st.session_state.user_id = ""

def login(user_id: str, password: str) -> bool:
    if user_id == "id01" and password == "pwd01":
        st.session_state.logged_in = True
        st.session_state.user_id = user_id
        return True
    return False

def logout() -> None:
    st.session_state.logged_in = False

def is_logged_in() -> bool:
    return st.session_state.logged_in
