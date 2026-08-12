import streamlit as st
from clients.user_client import login_process
from core.api_client import BackendAPIError
from streamlit_session_browser_storage import SessionStorage

def init_state():
    storage = SessionStorage()
    access_token = storage.getItem("access_token") or ""
    login_id = storage.getItem("login_id") or ""

    st.session_state.access_token = access_token
    st.session_state.user_id = login_id

def login(login_id:str, login_pwd:str) -> dict:
    try:
        payload = {"login_id" : login_id, "password" : login_pwd}
        result = login_process(payload)
        if result["access_token"] is not None:
            st.session_state.user_id  = login_id
            st.session_state.access_token = result["access_token"]
        return result
    except BackendAPIError as error :
        st.error(str(error))

def logout() -> None:
    storage = SessionStorage()
    st.session_state.access_token = ""
    st.session_state.user_id = ""

    storage.eraseItem("access_token", key="erase_access_token")
    storage.eraseItem("login_id", key="erase_login_id")

    storage.storedItems.pop("access_token", None)
    storage.storedItems.pop("login_id", None)

def is_logged_in() -> bool:
    storage = SessionStorage()
    access_token = storage.getItem("access_token") or ""

    return bool(access_token)