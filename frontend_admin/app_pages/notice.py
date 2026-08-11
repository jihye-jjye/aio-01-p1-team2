import streamlit as st
from clients.notice_client import notice_all_process
from core.api_client import BackendAPIError

st.title("공지사항 관리")

try:
    response = notice_all_process()
    if response is not None:
        st.write("data confirm")
except BackendAPIError as error:
    st.warning(str(error))