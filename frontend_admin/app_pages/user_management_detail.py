import streamlit as st
from core.api_client import BackendAPIError, request
from clients.user_client import user_get_detail_process

if st.button("←뒤로 가기"):
    st.switch_page("app_pages/user_management.py")

try:
    # response = user_get_detail_process(st.session_state.selected_item_login_id)
    # account_info = response["account"]
    # quest_info = response["quests"]

    with st.container :
        image_col , userinfo_col, user_detail_col = st.columns(3)
        with image_col :
            st.image("./resources/캐릭터.png", width=50)
        with userinfo_col:
            st.title("")
        with user_detail_col:
            st.text("")

    profile_tab, quest_tab, last_login_tab,  = st.tabs(["프로필", "퀘스트 진행", "접속기록"])
    
    with profile_tab:
        st.write("profile info")
    with quest_tab:
        st.write("quest info")
    with last_login_tab:
        st.write("last login info")
    

except BackendAPIError as error :
    st.write(str(error))