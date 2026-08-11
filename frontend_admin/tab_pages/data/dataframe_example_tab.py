import streamlit as st
import pandas as pd
from core.auth_sample import is_logged_in
from core.api_client import BACKEND_URL, BackendAPIError
from clients.example_client import product_create, product_get_all, product_delete, product_update

@st.dialog("create")
def create_product() -> None:
    st.info("product create")
    with st.form(f"form_create") :
        # create_id = st.number_input("id", min_value=1, value=1)
        create_name = st.text_input("name", value="빨대")
        create_price = st.number_input("price", min_value=1000, value=10000)
        if st.form_submit_button("create") : 
            with st.spinner("create request ing...."):
               response = product_create(create_name, int(create_price))
            if response:
                st.rerun()

@st.dialog("update")
def update_product(selected_row_data) :
    with st.expander("update data"):
        product_id = st.number_input("id", value=selected_row_data["id"], disabled=True)
        update_name = st.text_input("id", value=selected_row_data["name"])
        update_price = st.number_input("id", value=selected_row_data["price"])
        # st.write(selected_row_data)
        if st.button("update") :
            with st.spinner("update request ing...."):
                payload = {"name": update_name, "price" : update_price}
                # response = httpx.put(f"{server_URL}/product/update/{product_id}", json=payload, timeout=5.0)
                response = product_update()
            if response:
                st.rerun()

@st.dialog("delete")
def delete_product(selected_row_data) : 
    with st.expander("delete data"):
        product_id = st.text_input("id", value=selected_row_data["id"], disabled=True)
        # st.write(selected_row_data)
        if st.button("delete") :
            with st.spinner("delete request ing...."):
                # response = httpx.delete(f"{server_URL}/product/delete/{product_id}", timeout=5.0)
                response = product_delete(product_id)
            if response:
                st.rerun()

def show_products():
    if not is_logged_in():
            st.warning("로그인이 필요한 화면입니다.")
            return
    
    with st.container(border=True) :
        st.subheader("상품 조회", divider="rainbow")
        with st.spinner("Product Selecting.....") :
            response = product_get_all()
            items = response.get("data") or []

            if not items:
                st.info("해당 상품이 없습니다.")
                return
            df = pd.DataFrame(items)
            select_event = st.dataframe(items, use_container_width=True, selection_mode="single-row", on_select="rerun")
            if select_event.selection.rows :
                row_index = select_event.selection.rows[0]
                selected_row = df.iloc[row_index].to_dict()
                st.write("선택된 상품:", selected_row)
                update_col, delete_col = st.columns(2)
                with update_col :
                    if st.button("update", use_container_width=True):
                        update_product(selected_row)
                with delete_col :
                    if st.button("delete", use_container_width=True) :
                        delete_product(selected_row)
            else :
                if st.button("create", use_container_width=True) :
                    create_product()
    # # chart example 
    # st.line_chart(df)
            