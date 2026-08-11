import streamlit as st
from core.api_client import BackendAPIError, request
from clients.user_client import user_get_detail_process, user_get_overview_process
from tab_pages.data.profile_tab import show_profile
from tab_pages.data.quest_tab import show_quest

if st.button("←뒤로 가기"):
    st.switch_page("app_pages/user_management.py")

try:
    # response = user_get_detail_process(st.session_state.selected_item_login_id)
    response = user_get_overview_process(st.session_state.selected_item_login_id)
    account_info = response["account"]
    profile_info = account_info["profile"]
    quest_info = response["quests"]

    if response is not None:
        with st.container(border=True) :
            image_col , userinfo_col, user_detail_col = st.columns([0.5,1,1])
            with image_col :
                st.image("./resources/캐릭터.png", width=70)
            with userinfo_col:
                st.title(account_info["login_id"])
                st.text("사용자" if account_info["role"] == "user" else account_info["role"])
            with user_detail_col:
                st.text("사용자" if account_info["role"] == "user" else account_info["role"])
                st.text(account_info["created_at"])
                st.text("활성" if account_info["is_active"] else "비활성")

    profile_tab, quest_tab, last_login_tab,  = st.tabs(["프로필", "퀘스트 진행", "접속기록"])
    
    with profile_tab:
        st.write("profile info")
        show_profile(profile_info)
    with quest_tab:
        st.write("quest info")
        show_quest(quest_info)
    with last_login_tab:
        st.write("last login info")
    

except BackendAPIError as error :
    st.write(str(error))