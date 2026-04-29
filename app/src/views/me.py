"""Me / Profile HTML views."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from ..deps import CurrentUser, CurrentTenant, DBSession, RedisClient
from ._context import build_base_context

router = APIRouter(tags=["views"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/me", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    user: CurrentUser,
    tenant: CurrentTenant,
    db: DBSession,
    redis: RedisClient,
) -> HTMLResponse:
    ctx = await build_base_context(request, user, tenant, db, redis)
    return templates.TemplateResponse(request, "me/profile.html", ctx)
