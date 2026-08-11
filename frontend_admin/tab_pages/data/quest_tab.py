import streamlit as st

def show_quest(quests : dict):
    st.dataframe(quests)