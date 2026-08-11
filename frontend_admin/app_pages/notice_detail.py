import streamlit as st
from clients.notice_client import notice_get_process
from core.api_client import BackendAPIError

if st.button("←뒤로 가기"):
    st.switch_page("app_pages/notice.py")
try:
    response = notice_get_process(st.session_state.selected_item_notice_id)
    with st.container(border=True):
        if response is not None:
            text_col, value_col, batch_col = st.columns([1,1,3])
            with text_col:
                st.text("ID : ")
            with value_col:
                st.text(response["id"])
            with batch_col:
                st.text("")

except BackendAPIError as error:
    st.warning(str(error))

