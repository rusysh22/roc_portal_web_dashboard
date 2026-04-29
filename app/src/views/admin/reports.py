"""Admin: Report management HTML views."""
from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy import select

from ...core.rbac import require_permission
from ...deps import CurrentUser, CurrentTenant, DBSession, RedisClient
from ...models.user import Role
from .._context import build_base_context

router = APIRouter(tags=["admin-views"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent.parent / "templates"))


@router.get(
    "/admin/reports",
    response_class=HTMLResponse,
    dependencies=[require_permission("report.manage")],
)
async def reports_admin_page(
    request: Request,
    user: CurrentUser,
    tenant: CurrentTenant,
    db: DBSession,
    redis: RedisClient,
) -> HTMLResponse:
    result = await db.execute(
        select(Role).where(Role.tenant_id == tenant.id).order_by(Role.name)
    )
    roles = result.scalars().all()
    roles_json = json.dumps([{"id": r.id, "name": r.name} for r in roles])

    ctx = await build_base_context(request, user, tenant, db, redis, extra={"roles_json": roles_json})
    return templates.TemplateResponse(request, "admin/reports.html", ctx)
