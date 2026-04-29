"""Admin: Role management HTML views."""
from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy import select

from ...core.rbac import require_permission
from ...deps import CurrentUser, CurrentTenant, DBSession, RedisClient
from ...models.user import Permission
from .._context import build_base_context

router = APIRouter(tags=["admin-views"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent.parent / "templates"))


@router.get(
    "/admin/roles",
    response_class=HTMLResponse,
    dependencies=[require_permission("role.manage")],
)
async def roles_page(
    request: Request,
    user: CurrentUser,
    tenant: CurrentTenant,
    db: DBSession,
    redis: RedisClient,
) -> HTMLResponse:
    perms_result = await db.execute(select(Permission).order_by(Permission.code))
    permissions = perms_result.scalars().all()
    permissions_json = json.dumps([
        {"id": p.id, "code": p.code, "description": p.description}
        for p in permissions
    ])

    ctx = await build_base_context(request, user, tenant, db, redis, extra={"permissions_json": permissions_json})
    return templates.TemplateResponse(request, "admin/roles.html", ctx)
