from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.api.router import router
from app.core.config import get_settings
from app.core.logging import configure_logging


settings = get_settings()
configure_logging()

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie=settings.session_cookie_name,
        same_site="lax",
        https_only=settings.app_env == "production",
    )
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

    app.state.settings = settings
    app.state.templates = templates

    @app.exception_handler(403)
    async def forbidden_handler(request: Request, exc: HTTPException) -> HTMLResponse:
        accept = request.headers.get("accept", "").lower()
        if "text/html" not in accept:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": exc.detail if isinstance(exc.detail, str) else "Forbidden"},
            )
        return templates.TemplateResponse(
            name="system/403.html",
            context={
                "request": request,
                "page_title": "Access Denied",
                "demo_admin_email": str(settings.demo_admin_email),
                "demo_admin_password": settings.demo_admin_password,
            },
            request=request,
            status_code=status.HTTP_403_FORBIDDEN,
        )

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: HTTPException) -> HTMLResponse:
        return templates.TemplateResponse(
            name="system/404.html",
            context={"request": request, "page_title": "Page Not Found"},
            request=request,
            status_code=status.HTTP_404_NOT_FOUND,
        )

    @app.exception_handler(Exception)
    async def server_error_handler(request: Request, exc: Exception) -> HTMLResponse:
        return templates.TemplateResponse(
            name="system/500.html",
            context={"request": request, "page_title": "Unexpected Error"},
            request=request,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    @app.get("/sw.js", include_in_schema=False)
    async def service_worker() -> FileResponse:
        return FileResponse(
            path=BASE_DIR / "static" / "sw.js",
            media_type="application/javascript",
            headers={"Service-Worker-Allowed": "/"},
        )

    app.include_router(router)
    return app


app = create_app()
