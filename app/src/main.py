"""FastAPI application factory and entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import get_settings
from .core.tenant import TenantMiddleware
from .i18n import detect_locale, translate

logging.basicConfig(format="%(message)s", level=logging.INFO)
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)
log = structlog.get_logger()

BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    settings = get_settings()
    log.info("app.startup", env=settings.app_env, name=settings.app_name)
    yield
    log.info("app.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/api/docs" if not settings.is_production else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── Middleware (order matters: outermost first) ────────────────────────────
    if settings.is_production:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts_list)
    app.add_middleware(TenantMiddleware)

    # ── Static files ──────────────────────────────────────────────────────────
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # ── Security headers middleware ───────────────────────────────────────────
    @app.middleware("http")
    async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=(), fullscreen=(self)"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.powerbi.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "frame-src https://app.powerbi.com https://*.powerbi.com; "
            "connect-src 'self' https://api.powerbi.com;"
        )
        return response

    # ── Routers ───────────────────────────────────────────────────────────────
    from .api.auth import router as auth_api_router
    from .api.me import router as me_api_router
    from .api.reports import router as reports_api_router
    from .api.export import router as export_api_router
    from .api.admin.users import router as admin_users_api_router
    from .api.admin.roles import router as admin_roles_api_router
    from .api.admin.permissions import router as admin_permissions_api_router
    from .api.admin.reports import router as admin_reports_api_router
    from .api.admin.config import router as admin_config_api_router
    from .api.admin.departments import router as admin_departments_api_router
    from .views.auth import router as auth_view_router
    from .views.dashboard import router as dashboard_view_router
    from .views.me import router as me_view_router
    from .views.reports import router as reports_view_router
    from .views.admin.users import router as admin_users_view_router
    from .views.admin.roles import router as admin_roles_view_router
    from .views.admin.reports import router as admin_reports_view_router
    from .views.admin.config import router as admin_config_view_router
    from .views.admin.departments import router as admin_departments_view_router

    app.include_router(auth_api_router)
    app.include_router(me_api_router)
    app.include_router(reports_api_router)
    app.include_router(export_api_router)
    app.include_router(admin_users_api_router)
    app.include_router(admin_roles_api_router)
    app.include_router(admin_permissions_api_router)
    app.include_router(admin_reports_api_router)
    app.include_router(admin_config_api_router)
    app.include_router(admin_departments_api_router)
    app.include_router(auth_view_router)
    app.include_router(dashboard_view_router)
    app.include_router(me_view_router)
    app.include_router(reports_view_router)
    app.include_router(admin_users_view_router)
    app.include_router(admin_roles_view_router)
    app.include_router(admin_reports_view_router)
    app.include_router(admin_config_view_router)
    app.include_router(admin_departments_view_router)

    # ── Built-in routes ───────────────────────────────────────────────────────
    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @app.get("/", include_in_schema=False)
    async def index(request: Request):
        from fastapi.responses import RedirectResponse
        access_token = request.cookies.get("access_token")
        if access_token:
            return RedirectResponse("/dashboard", status_code=302)
        return RedirectResponse("/login", status_code=302)

    log.info("app.created", env=settings.app_env)
    return app


app = create_app()
