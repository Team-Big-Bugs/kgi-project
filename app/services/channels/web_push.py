from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urljoin

from py_vapid import Vapid01
from pywebpush import WebPushException, webpush
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings, normalize_base_url
from app.core.logging import get_logger
from app.db.models.user import User
from app.db.models.web_push_subscription import WebPushSubscription


logger = get_logger(__name__)


def _resolve_vapid_private_key(private_key_value: str) -> Vapid01 | str:
    normalized = private_key_value.strip()
    if Path(normalized).is_file():
        return normalized
    if "\\n" in normalized:
        normalized = normalized.replace("\\n", "\n")
    if "-----BEGIN" in normalized:
        return Vapid01.from_pem(normalized.encode("utf-8"))
    return normalized


class WebPushSender:
    def send(self, *, db: Session, user: User, title: str, body: str, tracking_url: str) -> None:
        settings = get_settings()
        if not settings.vapid_public_key or not settings.vapid_private_key:
            raise RuntimeError("VAPID keys are not configured")
        vapid_private_key = _resolve_vapid_private_key(settings.vapid_private_key)

        subscriptions = list(
            db.scalars(
                select(WebPushSubscription)
                .where(WebPushSubscription.user_id == user.id, WebPushSubscription.is_active.is_(True))
                .order_by(
                    WebPushSubscription.last_seen_at.desc().nulls_last(),
                    WebPushSubscription.updated_at.desc(),
                    WebPushSubscription.id.desc(),
                )
            )
        )
        if not subscriptions:
            raise ValueError("No active web push subscription found")

        payload = {
            "title": title,
            "body": body,
            "url": urljoin(f"{normalize_base_url(settings.app_base_url)}/", tracking_url.lstrip("/")),
        }
        last_error: Exception | None = None
        success_count = 0

        for subscription in subscriptions:
            if not subscription.endpoint or not subscription.p256dh_key or not subscription.auth_key:
                subscription.is_active = False
                db.add(subscription)
                db.commit()
                continue

            try:
                webpush(
                    subscription_info={
                        "endpoint": subscription.endpoint,
                        "keys": {"p256dh": subscription.p256dh_key, "auth": subscription.auth_key},
                    },
                    data=json.dumps(payload),
                    vapid_private_key=vapid_private_key,
                    vapid_claims={"sub": settings.vapid_subject},
                    ttl=3600,
                )
                subscription.last_seen_at = datetime.now(timezone.utc)
                db.add(subscription)
                db.commit()
                success_count += 1
            except WebPushException as exc:
                last_error = exc
                response = getattr(exc, "response", None)
                status_code = getattr(response, "status_code", None)
                if status_code in {404, 410}:
                    subscription.is_active = False
                    db.add(subscription)
                    db.commit()
                    logger.info(
                        "Deactivated expired web push subscription for user_id=%s endpoint=%s status=%s",
                        user.id,
                        subscription.endpoint,
                        status_code,
                    )
                    continue
                logger.exception("Web push dispatch failed for user_id=%s endpoint=%s", user.id, subscription.endpoint)
            except Exception as exc:  # pragma: no cover - external integration failures
                last_error = exc
                logger.exception("Unexpected web push failure for user_id=%s endpoint=%s", user.id, subscription.endpoint)

        if success_count:
            logger.info("Web push dispatched to %s active subscription(s) for user_id=%s", success_count, user.id)
            return
        if last_error is not None:
            raise RuntimeError(f"Web push failed: {last_error}") from last_error
        raise RuntimeError("Web push failed: no usable subscription could be delivered")
