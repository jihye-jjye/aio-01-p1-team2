from fastapi import APIRouter

from app.api.routes import (
    auth,
    notices,
    onboarding,
    plan_proposals,
    plans,
    profile,
    quests,
    saved_jobs,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(onboarding.router)
api_router.include_router(profile.router)
api_router.include_router(plan_proposals.router)
api_router.include_router(plans.router)
api_router.include_router(notices.router)
api_router.include_router(quests.router)
api_router.include_router(saved_jobs.router)
