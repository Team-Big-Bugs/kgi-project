from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes._common import require_user
from app.core.config import get_settings
from app.db.models.web_push_subscription import WebPushSubscription
from app.db.session import get_db
from app.schemas.notifications import PushPublicKeyResponse, PushSubscriptionCreate, PushSubscriptionRead, PushUnsubscribeRequest
from app.services.channels.web_push import WebPushSender


settings = get_settings()
router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/push/public-key")
def get_push_public_key():
    if not settings.vapid_public_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="VAPID public key is not configured")
    return {"public_key": settings.vapid_public_key, "key": settings.vapid_public_key}


@router.post("/push/subscribe")
def subscribe_push(payload: PushSubscriptionCreate, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    subscription = db.scalar(select(WebPushSubscription).where(WebPushSubscription.endpoint == payload.endpoint))
    if subscription is None:
        subscription = WebPushSubscription(
            user_id=user.id,
            endpoint=payload.endpoint,
            p256dh_key=payload.p256dh_key,
            auth_key=payload.auth_key,
            is_active=True,
            last_seen_at=datetime.now(timezone.utc),
        )
    else:
        subscription.user_id = user.id
        subscription.p256dh_key = payload.p256dh_key
        subscription.auth_key = payload.auth_key
        subscription.is_active = True
        subscription.last_seen_at = datetime.now(timezone.utc)
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return {"ok": True, "subscription": PushSubscriptionRead.model_validate(subscription).model_dump(mode="json")}


@router.post("/push/unsubscribe")
def unsubscribe_push(payload: PushUnsubscribeRequest, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    subscription = db.scalar(
        select(WebPushSubscription).where(
            WebPushSubscription.user_id == user.id,
            WebPushSubscription.endpoint == payload.endpoint,
        )
    )
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    subscription.is_active = False
    db.add(subscription)
    db.commit()
    return {"ok": True, "subscription": PushSubscriptionRead.model_validate(subscription).model_dump(mode="json")}


@router.post("/push/test")
def test_push_notification(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    sender = WebPushSender()
    try:
        sender.send(
            db=db,
            user=user,
            title="Smart Nudge test",
            body="Your web push channel is working. This is a local verification nudge.",
            tracking_url="/dashboard",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Push test failed: {exc}",
        ) from exc
    return {"ok": True, "message": "Test push dispatched"}
