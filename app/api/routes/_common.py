from __future__ import annotations

from datetime import datetime, time
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from jinja2 import TemplateNotFound
from sqlalchemy.orm import Session

from app.core.security import current_user_id
from app.db.models.agent_preference import AgentPreference
from app.db.models.user import User


def render_or_json(
    request: Request,
    template_name: str,
    context: dict[str, Any],
    fallback_payload: Any,
    *,
    status_code: int = status.HTTP_200_OK,
):
    templates = getattr(request.app.state, "templates", None)
    if templates is not None:
        try:
            templates.env.get_template(template_name)
        except TemplateNotFound:
            pass
        else:
            template_context = {"request": request, **context}
            return templates.TemplateResponse(
                name=template_name,
                context=template_context,
                request=request,
                status_code=status_code,
            )
    return JSONResponse(content=jsonable_encoder(fallback_payload), status_code=status_code)


def expects_html(request: Request) -> bool:
    accept = request.headers.get("accept", "").lower()
    content_type = request.headers.get("content-type", "").lower()
    return "text/html" in accept or "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type


def expects_json(request: Request) -> bool:
    content_type = request.headers.get("content-type", "").lower()
    accept = request.headers.get("accept", "").lower()
    return "application/json" in content_type or ("application/json" in accept and "text/html" not in accept)


def require_user(request: Request, db: Session) -> User:
    user_id = current_user_id(request)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            detail="Authentication required",
            headers={"Location": "/auth/login"},
        )

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            detail="Authentication required",
            headers={"Location": "/auth/login"},
        )
    return user


def require_admin_user(request: Request, db: Session) -> User:
    user = require_user(request, db)
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


def parse_time_value(value: Any) -> time | None:
    if value in (None, "", "null"):
        return None
    if isinstance(value, time):
        return value
    text = str(value).strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid time value: {value}")


def format_time_value(value: time | None) -> str | None:
    return value.strftime("%H:%M") if value else None


def preference_payload(preference: AgentPreference | None) -> dict[str, Any] | None:
    if preference is None:
        return None
    return {
        "agent_id": preference.agent_id,
        "preferred_channel": preference.preferred_channel,
        "dnd_start_time": format_time_value(preference.dnd_start_time),
        "dnd_end_time": format_time_value(preference.dnd_end_time),
        "is_opted_out": preference.is_opted_out,
        "peak_learning_time": format_time_value(preference.peak_learning_time),
    }
