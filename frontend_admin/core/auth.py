import streamlit as st
from clients.user_client import login_process
from core.api_client import BackendAPIError
from streamlit_session_browser_storage import SessionStorage

def init_state():
    if "access_token" not in st.session_state:
        st.session_state.access_token = ""

    if "user_id" not in st.session_state:
        st.session_state.user_id = ""

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
    st.session_state.access_token = ""
    st.session_state.user_id = ""

def is_logged_in() -> bool:
    # return True
    return bool(st.session_state.access_token)

