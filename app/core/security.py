from __future__ import annotations

from fastapi import HTTPException, Request, status
from werkzeug.security import check_password_hash, generate_password_hash


SESSION_USER_ID_KEY = "user_id"
SESSION_ROLE_KEY = "role"


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, password)


def set_session_auth(request: Request, user_id: int, role: str) -> None:
    request.session[SESSION_USER_ID_KEY] = user_id
    request.session[SESSION_ROLE_KEY] = role


def clear_session_auth(request: Request) -> None:
    request.session.clear()


def current_user_id(request: Request) -> int | None:
    raw = request.session.get(SESSION_USER_ID_KEY)
    return int(raw) if raw is not None else None


def current_role(request: Request) -> str | None:
    return request.session.get(SESSION_ROLE_KEY)


def require_authenticated_user(request: Request) -> int:
    user_id = current_user_id(request)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            detail="Authentication required",
            headers={"Location": "/login"},
        )
    return user_id


def require_admin(request: Request) -> int:
    user_id = require_authenticated_user(request)
    role = current_role(request)
    if role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return user_id
