# product_router.py

from fastapi import APIRouter, HTTPException

from app.schemas.product_schema import ProductCreate, ProductUpdate
from app.services.product_service import (
    product_create,
    product_delete,
    product_get,
    product_get_all,
    product_update,
)
from app.core.api_response import ApiResponse

product_router = APIRouter(tags=["Product"])

# 200: 정상 - 정상 실행 되면 자동 전송
# 400: 잘못된 요청
# 401: 로그인 필요
# 403: 권한 없음
# 404: 데이터 없음
# 409: 중복 데이터
# 422: 입력값 검증 실패
# 500: 서버 또는 DB 처리 실패

# 1. create
@product_router.post("/product/create")
def create(product: ProductCreate) -> ApiResponse:
    created_product = product_create(product)
    
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

# 2. 한개 조회
@product_router.get("/product/get/{product_id}")
def get(product_id: str) -> ApiResponse:

    product = product_get(product_id)
    if product is None:
        raise HTTPException(
            status_code=404,
            detail=f"상품 ID {product_id}를 찾을 수 없습니다."
        )
    response = ApiResponse(
        success = True,
        message="상품 조회에 성공했습니다.",
        data = product
    )
    return response

# 3. 전체 조회
@product_router.get("/product/getall")
def get_all() -> ApiResponse:
    products = product_get_all()
    response = ApiResponse(
        success = True,
        message="상품 목록 조회에 성공했습니다.",
        data = products
    )
    return response

# 4. 한개 삭제
@product_router.delete("/product/delete/{product_id}")
def delete(product_id: str) -> ApiResponse:
    product = product_delete(product_id)
    if product is None:
        raise HTTPException(
            status_code=404,
            detail=f"상품 ID {product_id}를 찾을 수 없습니다."
        )
    response = ApiResponse(
        success = True,
        message="상품이 삭제되었습니다.",
        data = product
    )
    return response

# 5. 수정
# path-Parameter, request body가 arg로 들어간다.
@product_router.put("/product/{product_id}")
def update(product_id: str, product: ProductUpdate) -> ApiResponse:
    updated_product = product_update(product_id, product)
    if updated_product is None:
        raise HTTPException(
            status_code=404,
            detail=f"상품 ID {product_id}를 찾을 수 없습니다."
        )
    response = ApiResponse(
        success = True,
        message="상품이 수정되었습니다.",
        data = updated_product
    )
    return response
