from fastapi import APIRouter

from app.api.routes import admin, agent, auth, notifications, tracking, webhooks


router = APIRouter()
router.include_router(auth.router)
router.include_router(agent.router)
router.include_router(admin.router)
router.include_router(notifications.router)
router.include_router(tracking.router)
router.include_router(webhooks.router)
