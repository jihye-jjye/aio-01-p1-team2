import streamlit as st

from clients.user_client import login_process
from core.api_client import BackendAPIError
from streamlit_session_browser_storage import SessionStorage


def login(login_id: str, login_pwd: str) -> dict | None:
    try:
        result = login_process({"login_id": login_id, "password": login_pwd})

        if result.get("access_token"):
            st.session_state.user_id = login_id
            st.session_state.access_token = result["access_token"]

        return result
    except BackendAPIError as error:
        st.error(str(error))
        return None


def logout() -> None:
    storage = SessionStorage()

    st.session_state.access_token = ""
    st.session_state.user_id = ""

    storage.eraseItem("access_token", key="erase_access_token")
    storage.eraseItem("login_id", key="erase_login_id")
    storage.storedItems.pop("access_token", None)
    storage.storedItems.pop("login_id", None)
