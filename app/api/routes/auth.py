from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes._common import expects_html, render_or_json, require_user
from app.core.config import get_settings
from app.core.security import clear_session_auth, current_user_id, set_session_auth, verify_password
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import LoginRequest, UserSummary


settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])


def _login_page_context(
    *,
    email: str = "",
    next_url: str | None = None,
    error_message: str | None = None,
) -> dict[str, str | None]:
    return {
        "page_title": "Login",
        "page_subtitle": "Use a seeded demo account to explore the mobile-first agent and admin flows.",
        "login_action_url": "/auth/login",
        "demo_admin_email": str(settings.demo_admin_email),
        "demo_admin_password": settings.demo_admin_password,
        "demo_agent_email": str(settings.demo_agent_email),
        "demo_agent_password": settings.demo_agent_password,
        "email": email,
        "next_url": next_url,
        "error_message": error_message,
    }


@router.get("/login")
def login_page(request: Request):
    if current_user_id(request) is not None:
        next_url = "/dashboard"
        if request.session.get("role") == "admin":
            next_url = "/admin/dashboard"
        return RedirectResponse(url=next_url, status_code=status.HTTP_302_FOUND)
    return render_or_json(
        request,
        "agent/login.html",
        _login_page_context(next_url=request.query_params.get("next_url")),
        {
            "page": "login",
            **_login_page_context(next_url=request.query_params.get("next_url")),
        },
    )


@router.post("/login")
async def login(request: Request, db: Session = Depends(get_db)):
    if request.headers.get("content-type", "").lower().startswith("application/json"):
        payload_data = await request.json()
    else:
        form = await request.form()
        payload_data = {
            "email": form.get("email", ""),
            "password": form.get("password", ""),
            "next_url": form.get("next_url") or None,
        }

    try:
        payload = LoginRequest.model_validate(payload_data)
    except ValidationError:
        if expects_html(request):
            return render_or_json(
                request,
                "agent/login.html",
                _login_page_context(
                    email=str(payload_data.get("email", "")),
                    next_url=payload_data.get("next_url"),
                    error_message="Email and password are required.",
                ),
                {"ok": False, "detail": "Invalid email or password"},
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        raise

    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        if expects_html(request):
            return render_or_json(
                request,
                "agent/login.html",
                _login_page_context(
                    email=str(payload.email),
                    next_url=payload.next_url,
                    error_message="Invalid email or password.",
                ),
                {"ok": False, "detail": "Invalid email or password"},
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    set_session_auth(request, user.id, user.role)
    redirect_to = payload.next_url or ("/admin/dashboard" if user.role == "admin" else "/dashboard")
    if expects_html(request):
        return RedirectResponse(url=redirect_to, status_code=status.HTTP_303_SEE_OTHER)

    return {
        "ok": True,
        "redirect_to": redirect_to,
        "user": UserSummary.model_validate(user).model_dump(mode="json"),
    }


@router.get("/logout")
@router.post("/logout")
def logout(request: Request):
    clear_session_auth(request)
    if expects_html(request):
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)
    return {"ok": True, "redirect_to": "/auth/login"}


@router.get("/me")
def me(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    return {"user": UserSummary.model_validate(user).model_dump(mode="json")}
