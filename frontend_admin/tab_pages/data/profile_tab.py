import streamlit as st

def show_profile(profile : dict):
    if profile is not None:
        st.write(profile["target_role"])
    else:
        st.info("해당 프로필이 아직 생성되지 않았습니다.")