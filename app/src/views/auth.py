"""Auth HTML views (Jinja2 pages)."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from ..deps import CurrentUserOptional, DBSession, RedisClient
from ._context import build_auth_context

router = APIRouter(tags=["views"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    user: CurrentUserOptional,
    db: DBSession,
    redis: RedisClient,
) -> HTMLResponse:
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    tenant = getattr(request.state, "tenant", None)
    ctx = await build_auth_context(request, tenant, db, redis, extra={
        "error": request.query_params.get("error"),
    })
    return templates.TemplateResponse(request, "auth/login.html", ctx)


@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(
    request: Request,
    db: DBSession,
    redis: RedisClient,
) -> HTMLResponse:
    tenant = getattr(request.state, "tenant", None)
    ctx = await build_auth_context(request, tenant, db, redis, extra={
        "sent": "sent" in request.query_params,
    })
    return templates.TemplateResponse(request, "auth/forgot_password.html", ctx)


@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(
    request: Request,
    db: DBSession,
    redis: RedisClient,
) -> HTMLResponse:
    tenant = getattr(request.state, "tenant", None)
    ctx = await build_auth_context(request, tenant, db, redis, extra={
        "token": request.query_params.get("token", ""),
    })
    return templates.TemplateResponse(request, "auth/reset_password.html", ctx)
