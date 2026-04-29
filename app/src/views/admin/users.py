"""Admin: User management HTML views."""
from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ...core.rbac import require_permission
from ...deps import CurrentUser, CurrentTenant, DBSession, RedisClient
from ...models.department import Department
from ...models.user import Role
from .._context import build_base_context

router = APIRouter(tags=["admin-views"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent.parent / "templates"))


@router.get(
    "/admin/users",
    response_class=HTMLResponse,
    dependencies=[require_permission("user.manage")],
)
async def users_page(
    request: Request,
    user: CurrentUser,
    tenant: CurrentTenant,
    db: DBSession,
    redis: RedisClient,
) -> HTMLResponse:
    roles = (await db.execute(
        select(Role).where(Role.tenant_id == tenant.id).order_by(Role.name)
    )).scalars().all()

    depts = (await db.execute(
        select(Department).where(Department.tenant_id == tenant.id).order_by(Department.name)
    )).scalars().all()

    roles_json = json.dumps([{"id": r.id, "name": r.name} for r in roles])
    depts_json = json.dumps([{"id": d.id, "name": d.name} for d in depts])

    ctx = await build_base_context(
        request, user, tenant, db, redis,
        extra={"roles_json": roles_json, "depts_json": depts_json},
    )
    return templates.TemplateResponse(request, "admin/users.html", ctx)
