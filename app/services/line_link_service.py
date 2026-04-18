from __future__ import annotations

import base64
import io
import secrets
from datetime import datetime, timedelta, timezone

import qrcode
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.line_link_request import LineLinkRequest
from app.db.models.user import User


logger = get_logger(__name__)


def normalize_link_code(link_code: str) -> str:
    return link_code.strip().upper()


def generate_link_code(db: Session, *, user: User) -> LineLinkRequest:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    for request in db.scalars(
        select(LineLinkRequest).where(LineLinkRequest.user_id == user.id, LineLinkRequest.status == "pending")
    ):
        request.status = "cancelled"
        db.add(request)

    code = f"LINK-{secrets.token_hex(4).upper()}"
    link_request = LineLinkRequest(
        user_id=user.id,
        link_code=code,
        expires_at=now + timedelta(minutes=settings.link_code_expiry_minutes),
        status="pending",
    )
    db.add(link_request)
    db.commit()
    db.refresh(link_request)
    return link_request


def build_qr_data_uri(payload: str) -> str:
    if not payload.strip():
        raise ValueError("QR payload cannot be empty")

    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode('ascii')}"


def link_line_user(db: Session, *, line_user_id: str, link_code: str) -> User | None:
    normalized_code = normalize_link_code(link_code)
    normalized_line_user_id = line_user_id.strip()
    if not normalized_code or not normalized_line_user_id:
        return None

    stmt = select(LineLinkRequest).where(LineLinkRequest.link_code == normalized_code)
    request = db.scalar(stmt)
    if request is None:
        return None
    now = datetime.now(timezone.utc)
    if request.status not in {"pending", "linked"}:
        return None
    request_expiry = request.expires_at
    compare_now = now
    if request_expiry.tzinfo is None:
        compare_now = datetime.utcnow()
    if request_expiry < compare_now and request.status != "linked":
        request.status = "expired"
        db.add(request)
        db.commit()
        return None

    user = db.get(User, request.user_id)
    if user is None:
        return None

    existing_user = db.scalar(select(User).where(User.line_user_id == normalized_line_user_id))
    if existing_user is not None and existing_user.id != user.id:
        request.status = "cancelled"
        db.add(request)
        db.commit()
        logger.info(
            "Rejected LINE linking because user_id=%s is already linked to another account",
            normalized_line_user_id,
        )
        return None

    user.line_user_id = normalized_line_user_id
    request.status = "linked"
    if request.consumed_at is None:
        request.consumed_at = now
    db.add_all([user, request])
    db.commit()
    db.refresh(user)
    return user


def extract_link_code_from_webhook_event(event: dict[str, object]) -> str | None:
    event_type = str(event.get("type", "")).strip().lower()
    source = event.get("source")
    if event_type != "message" or not isinstance(source, dict):
        return None

    message = event.get("message")
    if not isinstance(message, dict):
        return None
    if str(message.get("type", "")).strip().lower() != "text":
        return None

    text = message.get("text")
    if not isinstance(text, str):
        return None

    for token in text.split():
        code = normalize_link_code(token)
        if code.startswith("LINK-"):
            return code
    return None
