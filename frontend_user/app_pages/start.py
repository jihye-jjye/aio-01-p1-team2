import streamlit as st

from tab_pages.start.home_tab import show_home
from tab_pages.start.signup_tab import show_signup


home_tab, signup_tab = st.tabs(["홈", "회원가입"])

with home_tab:
    show_home()

with signup_tab:
    show_signup()
