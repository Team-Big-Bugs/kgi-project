from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.session import get_db
from app.schemas.webhooks import LineWebhookResponse
from app.services.channels.line import LineSender, verify_line_signature
from app.services.line_link_service import extract_link_code_from_webhook_event, link_line_user


router = APIRouter(prefix="/line", tags=["line"])
logger = get_logger(__name__)


@router.post("/webhook")
async def line_webhook(
    request: Request,
    x_line_signature: str | None = Header(default=None, alias="X-Line-Signature"),
    db: Session = Depends(get_db),
):
    body = await request.body()
    if not verify_line_signature(body, x_line_signature):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid LINE signature")

    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload") from exc

    processed = 0
    linked = 0
    ignored = 0

    for event in payload.get("events", []):
        processed += 1
        source = event.get("source", {})
        if not isinstance(source, dict) or "userId" not in source:
            ignored += 1
            continue

        link_code = extract_link_code_from_webhook_event(event)
        if link_code is None:
            ignored += 1
            continue

        user = link_line_user(db, line_user_id=source["userId"], link_code=link_code)
        if user is None:
            ignored += 1
            continue

        reply_token = event.get("replyToken")
        if isinstance(reply_token, str) and reply_token.strip():
            try:
                LineSender().reply_text(
                    reply_token=reply_token,
                    text=(
                        f"LINE connected successfully for {user.name}.\n"
                        "You can go back to Smart Nudge and keep LINE as your preferred channel."
                    ),
                )
            except Exception:
                logger.exception("Failed to send LINE link confirmation reply for user_id=%s", user.id)
        linked += 1

    return {"ok": True, "result": LineWebhookResponse(processed=processed, linked=linked, ignored=ignored).model_dump(mode="json")}
