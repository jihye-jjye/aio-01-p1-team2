# product_router.py

from fastapi import APIRouter
from app.schemas.auth_schema import (
    AuthLogin, AuthPublic, AuthCreate, AuthUpdate
)
from app.services.auth_service import (
    sign_up_process, sign_in_process, 
    sign_out_process, my_page_process,
    update_process
)

auth_router = APIRouter(tags=["Auth"])

@auth_router.post("/auth/create")
def create(auth:AuthCreate) -> AuthPublic:
    """신규 입력"""
    return sign_up_process(auth)

@auth_router.put("/auth/update")
def update(auth:AuthUpdate) -> AuthPublic:
    """업데이트 """
    return update_process(auth)

@auth_router.post("/auth/signin")
def signin(auth:AuthLogin) -> AuthPublic:
    return sign_in_process(auth)

@auth_router.get("/auth/signout/{input_id}")
def signout(input_id:str) -> AuthPublic:
    return sign_out_process(input_id)

@auth_router.get("/auth/mypage/{input_id}")
def mypage(input_id:str) -> AuthPublic:
    """ 회원 마이페이지 - ID를 입력하면 해당 회원의 정보(id, name)를 반환 """
    return my_page_process(input_id)
