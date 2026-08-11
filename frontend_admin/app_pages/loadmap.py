import streamlit as st
from clients.loadmap_client import loadmap_from_user
from streamlit_session_browser_storage import SessionStorage


session_storage = SessionStorage()
st.write("loadmap page")
# response = loadmap_from_user(st.session_state.user_id)
