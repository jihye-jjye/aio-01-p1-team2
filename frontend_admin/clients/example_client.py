from datetime import date
from typing import Any

from core.api_client import request

def create_item(name:str, price:int, desc:str, image: Any = None):
    """  로그인 진행 ID와 PWD 입력 하면 사용자 정보 리턴"""
    files = None
    if image is not None:
        files = {
            "image": (
                image.name,
                image.getvalue(),
                image.type or "application/octet-stream",
            )
        }

    # multiple/form-data 형식일 경우 아래와 같이 request를 날려야한다. 
    return request("POST", "/item/create",data={"name": name, "price": str(price), "desc": desc},files=files)
    # return request(
    #                 "POST", 
    #                 f"/item/create", 
    #                 data={"name": name, "price": str(price), "desc": desc},
    #                 files={"image": image} if image else None
    #                )


def get_items():
    return request("GET", "/item/select/all")

def get_item(item_id: int):
    return request("GET", f"/item/get/{item_id}")

def update_item(
    item_id: int,
    name: str,
    price: int,
    desc: str,
    image: Any = None,
):
    files = None
    if image is not None:
        files = {
            "image": (
                image.name,
                image.getvalue(),
                image.type or "application/octet-stream",
            )
        }

    return request(
        "PUT",
        f"/item/update/{item_id}",
        data={"name": name, "price": str(price), "desc": desc},
        files=files,
    )

def delete_item(item_id: int):
    return request("DELETE", f"/item/delete/{item_id}")

def search_item( name : str | None = None, start_date : date | None = None , end_date :date | None = None, 
    min_price : int | None = None, max_price: int | None = None):
    """Search"""
    param_data = {
        "name" : name,
        "start_date" : start_date,
        "end_date" : end_date,
        "min_price" : min_price,
        "max_price" : max_price
    }

    param_data = {k: v for k, v in param_data.items() if v is not None}
    
    # Query Parameters를 이용한 검색 기능 구현
    # ?aa=bb&cc=dd
    return request("GET", f"/item/search", params = param_data)