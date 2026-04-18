from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.services.tracking import mark_dispatch_opened


settings = get_settings()
router = APIRouter(prefix="/track", tags=["tracking"])


@router.get("/{tracking_token}")
def track_open(
    tracking_token: str,
    request: Request,
    assignment_id: int | None = None,
    db: Session = Depends(get_db),
):
    dispatch = mark_dispatch_opened(db, tracking_token)
    redirect_to = settings.tracking_redirect_fallback
    if dispatch is not None:
        redirect_to = f"/assignments/{assignment_id or dispatch.assignment.id}"
    return RedirectResponse(url=redirect_to, status_code=302)
