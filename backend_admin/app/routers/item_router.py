# item_router.py

from datetime import date
from typing import Annotated

from fastapi import (
    APIRouter, HTTPException, UploadFile, File, Form
)
from app.schemas.item_schema import ItemCreate
from app.services.image_service import save_image, delete_image
from app.services.item_service import (
    item_create,
    item_select_all,
    item_get,
    item_update,
    item_delete,
    item_search
)
from app.core.api_response import ApiResponse

item_router = APIRouter(tags=["Item"])

# 200: 정상 - 정상 실행 되면 자동 전송
# 400: 잘못된 요청
# 401: 로그인 필요
# 403: 권한 없음
# 404: 데이터 없음
# 409: 중복 데이터
# 422: 입력값 검증 실패
# 500: 서버 또는 DB 처리 실패

# 1. create
@item_router.post("/item/create")
async def create(
    name: Annotated[str, Form(min_length=1, max_length=50)],
    price: Annotated[int, Form(ge=1)],
    desc: Annotated[str, Form(min_length=1, max_length=200)],
    image: Annotated[UploadFile | None, File()] = None,
) -> ApiResponse:
    """아이템 등록"""
    image_url, image_filename = await save_image(image)
    item = ItemCreate(
        name=name,
        price=price,
        desc=desc,
        image_url=image_url,
        image_filename=image_filename,
    )
    # name, price, desc
    created_product = item_create(item)
    if created_product is None:
        raise HTTPException(
            status_code=500,
            detail="상품 등록에 실패했습니다.",
        )
    response = ApiResponse(
        success = True,
        message="상품이 등록되었습니다.",
        data = created_product
    )
    return response

@item_router.get("/item/get/{item_id}")
def get(item_id: int) -> ApiResponse:
    """아이템 개별 조회"""
    item = item_get(item_id)
    if item is None:
        raise HTTPException(
            status_code=404,
            detail=f"상품 ID {item_id}를 찾을 수 없습니다.",
        )
    return ApiResponse(
        success=True,
        message="상품을 조회했습니다.",
        data=item,
    )

# select all
@item_router.get("/item/select/all")
def select_all() -> ApiResponse:
    """아이템 전체 조회"""
    selected_product = item_select_all()
    if selected_product is None:
        raise HTTPException(
            status_code=404,
            detail="해당 데이터가 없습니다.",
        )

    response = ApiResponse(
        success = True,
        message="상품이 전체 조회되었습니다.",
        data = selected_product
    )
    return response

# Query Parameter를 이용한 검색 기능 구현
@item_router.get("/item/search")
def search(
    name : str | None = None, start_date : date | None = None , end_date :date | None = None, 
    min_price : int | None = None, max_price: int | None = None ) -> ApiResponse:
    """아이템 검색 기능 날짜는 '20260805' 형식으로 사용 해야한다."""
    ""

    # 서비스 호출 후 결과를 받아서 리턴
    # items = item_search( name, start_date, end_date,min_price, max_price) :  arg 순서 중요
    # 아래와 같이 쓰면 순서 상관없음
    items = item_search(
        name = name, start_date = start_date, end_date = end_date,
        min_price = min_price, max_price = max_price)
    
    return ApiResponse(
        success=True,
        message="상품을 검색하였습니다.",
        data=items,
    )

@item_router.put("/item/update/{item_id}")
async def update(
    item_id: int,
    name: Annotated[str, Form(min_length=1, max_length=50)],
    price: Annotated[int, Form(ge=1)],
    desc: Annotated[str, Form(min_length=1, max_length=200)],
    image: Annotated[UploadFile | None, File()] = None,
) -> ApiResponse:
    """아이템 수정"""
    current_item = item_get(item_id)
    if current_item is None:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")

    image_url = current_item.image_url
    image_filename = current_item.image_filename

    if image is not None and image.filename:
        new_image_url, new_image_filename = await save_image(image)
        image_url = new_image_url
        image_filename = new_image_filename

    updated_item = item_update(
        item_id=item_id,
        name=name,
        price=price,
        description=desc,
        image_url=image_url,
        image_filename=image_filename,
    )
    if updated_item is None:
        raise HTTPException(status_code=500, detail="상품 수정에 실패했습니다.")

    if image_filename != current_item.image_filename:
        delete_image(current_item.image_filename)

    return ApiResponse(
        success=True,
        message="상품을 수정했습니다.",
        data=updated_item,
    )

@item_router.delete("/item/delete/{item_id}")
def delete(item_id: int) -> ApiResponse:
    """아이템 삭제"""
    current_item = item_get(item_id)
    if current_item is None:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")

    deleted_item = item_delete(item_id)
    if deleted_item is None:
        raise HTTPException(status_code=500, detail="상품 삭제에 실패했습니다.")

    delete_image(current_item.image_filename)
    return ApiResponse(
        success=True,
        message="상품을 삭제했습니다.",
        data=deleted_item,
    )