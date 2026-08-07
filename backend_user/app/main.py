from fastapi import FastAPI
from app.routers.chat_router import chat_router
from app.routers.product_router import product_router
from app.routers.auth_router import auth_router
import app.core.chat_config
from app.routers.item_router import item_router  
from fastapi.staticfiles import StaticFiles
from app.core.upload_config import UPLOAD_DIR

# Swagger 문서(/docs)에 표시할 API 그룹 설명입니다.
tags_metadata = [
    {
        "name": "Auth",
        "description": "Sign up, in, out",
    },
    {
        "name": "Chat",
        "description": "Gemini 모델을 사용해 사용자 메시지에 답변합니다.",
    },
    {
        "name": "Product",
        "description": "Supabase에 저장된 상품을 생성·조회·수정·삭제합니다.",
    },
    {
        "name": "Item",
        "description": "Supabase에 저장된 상품을 생성·조회·수정·삭제합니다.",
    },
]
app = FastAPI(title="Main App", openapi_tags=tags_metadata)

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(product_router)
app.include_router(item_router)

