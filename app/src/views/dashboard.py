"""Dashboard HTML view."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..deps import CurrentUser, CurrentTenant, DBSession, RedisClient
from ..models.report import Report
from ._context import build_base_context

router = APIRouter(tags=["views"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    user: CurrentUser,
    tenant: CurrentTenant,
    db: DBSession,
    redis: RedisClient,
) -> HTMLResponse:
    role_ids = {r.id for r in user.roles}
    result = await db.execute(
        select(Report)
        .where(Report.tenant_id == tenant.id, Report.is_active == True)
        .options(selectinload(Report.roles))
        .order_by(Report.order_index, Report.name)
    )
    all_reports = result.scalars().all()

    if user.is_super_admin:
        reports = list(all_reports)
    else:
        reports = [r for r in all_reports if not r.roles or bool({role.id for role in r.roles} & role_ids)]

    ctx = await build_base_context(request, user, tenant, db, redis, extra={"reports": reports})
    # dashboard uses nav_reports built by build_base_context; no duplication
    return templates.TemplateResponse(request, "dashboard.html", ctx)
