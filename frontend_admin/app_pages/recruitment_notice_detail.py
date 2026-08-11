import streamlit as st
from core.api_client import BackendAPIError, request

st.header("채용 공고 등록 / 편집")

if st.button("←뒤로 가기"):
    st.switch_page("app_pages/recruitment_notice.py")

with st.form("recruitment_notice_detail_form"):
    