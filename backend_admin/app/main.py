from fastapi import FastAPI

from app.routers.admin_auth_router import admin_auth_router
from app.routers.admin_notice_router import admin_notice_router
from app.routers.admin_router import admin_router
from app.routers.dashboard_router import dashboard_router
from app.routers.feedback_router import feedback_router
from app.routers.saved_job_router import saved_job_router
from app.routers.user_admin_router import user_admin_router


tags_metadata = [
    {"name": "Admin Auth", "description": "관리자 로그인 및 인증 API"},
    {"name": "Admin", "description": "AI 로그 조회 및 KPI API"},
    {"name": "Admin Dashboard", "description": "관리자 대시보드 집계 API"},
    {"name": "User Admin", "description": "관리자용 회원 관리 API"},
    {"name": "Notice Admin", "description": "관리자용 공지사항 관리 API"},
    {"name": "Notice", "description": "공지사항 조회 API"},
    {
        "name": "Saved Job Admin",
        "description": "관리자용 저장된 취업 공고 조회 API",
    },
    {"name": "Feedback", "description": "AI 응답 피드백 API"},
]

app = FastAPI(title="Admin Backend", openapi_tags=tags_metadata)

app.include_router(admin_auth_router)
app.include_router(admin_router)
app.include_router(dashboard_router)
app.include_router(user_admin_router)
app.include_router(admin_notice_router)
app.include_router(saved_job_router)
app.include_router(feedback_router)
