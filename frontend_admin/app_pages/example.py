"""왼쪽 네비게이션 바에 조회 라는 버튼을 클릭 시 우측에 product, item tab을 만드는 부분"""
import streamlit as st

from frontend_user.core.auth_sample import is_logged_in
from frontend_user.tab_pages.data.item_search_example_tab import show_items
from frontend_user.tab_pages.data.dataframe_example_tab import show_products

if not is_logged_in():
    st.warning("로그인이 필요한 화면입니다.")
else:
    product_tab , item_tab = st.tabs(["Product", "Item"])

    with product_tab:
        show_products()
    with item_tab:
        show_items()