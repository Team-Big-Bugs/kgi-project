from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.web_push_subscription import WebPushSubscription


def upsert_push_subscription(
    db: Session,
    *,
    user_id: int,
    endpoint: str,
    p256dh_key: str,
    auth_key: str,
) -> WebPushSubscription:
    subscription = db.scalar(select(WebPushSubscription).where(WebPushSubscription.endpoint == endpoint))
    if subscription is None:
        subscription = WebPushSubscription(
            user_id=user_id,
            endpoint=endpoint,
            p256dh_key=p256dh_key,
            auth_key=auth_key,
            is_active=True,
            last_seen_at=datetime.now(timezone.utc),
        )
    else:
        subscription.user_id = user_id
        subscription.p256dh_key = p256dh_key
        subscription.auth_key = auth_key
        subscription.is_active = True
        subscription.last_seen_at = datetime.now(timezone.utc)

    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


def deactivate_push_subscription(db: Session, *, endpoint: str) -> None:
    subscription = db.scalar(select(WebPushSubscription).where(WebPushSubscription.endpoint == endpoint))
    if subscription is not None:
        subscription.is_active = False
        db.add(subscription)
        db.commit()
