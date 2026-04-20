from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.dispatch_log import DispatchLog


def mark_dispatch_opened(db: Session, tracking_token: str) -> DispatchLog | None:
    token = tracking_token.strip()
    if not token:
        return None

    dispatch = db.scalar(select(DispatchLog).where(DispatchLog.tracking_token == token))
    if dispatch is None:
        return None
    if dispatch.opened_timestamp is None:
        dispatch.opened_timestamp = datetime.now(timezone.utc)
        db.add(dispatch)
        db.commit()
        db.refresh(dispatch)
    return dispatch
