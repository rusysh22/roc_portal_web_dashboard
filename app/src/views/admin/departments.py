"""Admin: Department management HTML view."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ...core.rbac import require_permission
from ...deps import CurrentUser, CurrentTenant, DBSession, RedisClient
from ...models.department import Department
from .._context import build_base_context

router = APIRouter(tags=["admin-views"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent.parent / "templates"))


@router.get(
    "/admin/departments",
    response_class=HTMLResponse,
    dependencies=[require_permission("user.manage")],
)
async def departments_page(
    request: Request,
    user: CurrentUser,
    tenant: CurrentTenant,
    db: DBSession,
    redis: RedisClient,
) -> HTMLResponse:
    ctx = await build_base_context(request, user, tenant, db, redis)
    return templates.TemplateResponse(request, "admin/departments.html", ctx)
