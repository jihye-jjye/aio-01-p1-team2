import streamlit as st

def show_profile(profile : dict):
    st.write(profile["target_role"])