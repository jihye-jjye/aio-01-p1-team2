import streamlit as st

def show_quest(quests : dict):
    if quests is not None:
        st.dataframe(quests)
    else :
        st.info("해당 진행되어진 퀘스트가 없습니다.")