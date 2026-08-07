"""item 조회 관련 페이지가 실질적으로 뿌려지는 부분이다."""
import streamlit as st
from frontend_user.core.auth_sample import is_logged_in
from core.api_client import BACKEND_URL, BackendAPIError
from frontend_user.core.datetime_format import format_created_at
from frontend_user.clients.example_client import delete_item, get_item, get_items, update_item, search_item

def get_image_url(item: dict) -> str | None:
    image_url = item.get("image_url")
    if image_url and not image_url.startswith(("http://", "https://")):
        # 이미지 서버 경로를 가져와야해서 서버url을 넣어준것이다.
        return f"{BACKEND_URL}{image_url}"
    return image_url

def show_items() -> None:
    st.subheader("Items")

    if not is_logged_in():
        st.warning("로그인이 필요한 화면입니다.")
        return

    try:
        selected_item_id = st.session_state.get("selected_item_id")
        with st.form("item-search-form"):
            name_col, startdate_col, enddate_col, minprice_col, maxprice_col = st.columns(5)
            with name_col:
                search_name = st.text_input("상품명")
            with startdate_col:
                search_start_date = st.date_input("등록일 시작", value=None, min_value=None, max_value=None)
            with enddate_col:
                search_end_date = st.date_input("등록일 종료", value=None, min_value=None, max_value=None)
            with minprice_col:
                search_min_price = st.number_input("최소 가격", min_value=0, step=1000, value=0)
            with maxprice_col:
                search_max_price = st.number_input("최대 가격", min_value=0, step=1000, value=0)
    
            search_button = st.form_submit_button("Search")

        if selected_item_id is None:
            if message := st.session_state.pop("item_message", None):
                st.success(message)

            if search_button:
                response = search_item(search_name, search_start_date, search_end_date, search_min_price, search_max_price)
            else:
                response = get_items()
            # why? API Response 를 응답형태에서 data 를 가져오기 때문에..
            items = response.get("data") or []
        
            if not items:
                st.info("등록된 상품이 없습니다.")
                return
        
            st.caption(f"총 {len(items)}개의 상품")
        
            for item in items:
                with st.container(border=True):
                    image_column, info_column, button_column = st.columns([1, 4, 1])
        
                    with image_column:
                        image_url = get_image_url(item)
                        if image_url:
                            st.image(image_url, width=180)
                        else:
                            st.info("이미지 없음")
        
                    with info_column:
                        st.subheader(item.get("name") or "이름 없음")
                        st.write(f"가격: {int(item.get('price') or 0):,}원")
                        st.write(item.get("description") or "상품 설명이 없습니다.")
                        st.caption(
                            f"등록일: {format_created_at(item.get('created_at'))}"
                        )
        
                    with button_column:
                        if st.button("상세보기", key=f"item-tab-detail-{item['id']}"):
                            st.session_state.selected_item_id = item["id"]
                            st.rerun()

        else:
            response = get_item(st.session_state.selected_item_id)
            item = response.get("data") or {}
        
            if st.button("← 상품 목록으로"):
                st.session_state.pop("selected_item_id", None)
                st.rerun()
        
            if message := st.session_state.pop("item_message", None):
                st.success(message)
        
            st.title(item.get("name") or "상품 상세조회")
            image_column, info_column = st.columns([2, 3])
        
            with image_column:
                image_url = get_image_url(item)
                if image_url:
                    st.image(image_url, width=300)
                else:
                    st.info("이미지 없음")
        
            with info_column:
                st.subheader(f"{int(item.get('price') or 0):,}원")
                st.write(item.get("description") or "상품 설명이 없습니다.")
                st.caption(f"등록일: {format_created_at(item.get('created_at'))}")
        
            st.divider()
            st.subheader("상품 수정")
        
            with st.form(f"item-update-{st.session_state.selected_item_id}"):
                update_name = st.text_input("상품명", value=item.get("name") or "")
                update_price = st.number_input(
                    "가격",
                    min_value=1,
                    step=1000,
                    value=max(1, int(item.get("price") or 1)),
                )
                update_desc = st.text_area(
                    "상품 설명",
                    value=item.get("description") or "",
                )
                update_image = st.file_uploader(
                    "새 이미지 (선택하지 않으면 기존 이미지 유지)",
                    type=["jpg", "jpeg", "png"],
                )
                update_button = st.form_submit_button("수정하기")
        
            if update_button:
                if not update_name.strip() or not update_desc.strip():
                    st.error("상품명과 상품 설명을 입력해 주세요.")
                else:
                    result = update_item(
                        item_id=st.session_state.selected_item_id,
                        name=update_name.strip(),
                        price=int(update_price),
                        desc=update_desc.strip(),
                        image=update_image,
                    )
                    st.session_state.item_message = result.get(
                        "message", "상품을 수정했습니다."
                    )
                    st.rerun()
        
            st.divider()
            st.subheader("상품 삭제")
            delete_confirmed = st.checkbox(
                "삭제한 상품은 복구할 수 없습니다. 삭제에 동의합니다.",
                key=f"delete-confirm-{st.session_state.selected_item_id}",
            )
            if st.button(
                "상품 삭제",
                type="primary",
                disabled=not delete_confirmed,
                key=f"delete-tab-item-{st.session_state.selected_item_id}",
            ):
                result = delete_item(st.session_state.selected_item_id)
                st.session_state.pop("selected_item_id", None)
                st.session_state.item_message = result.get(
                    "message", "상품을 삭제했습니다."
                )
                st.rerun()

    except BackendAPIError as error:
        st.error(str(error))   