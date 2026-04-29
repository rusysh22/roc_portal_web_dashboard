"""Admin: Site configuration HTML view."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy import select

from ...core.rbac import require_permission
from ...deps import CurrentUser, CurrentTenant, DBSession, RedisClient
from ...models.config import SiteConfig
from .._context import build_base_context

router = APIRouter(tags=["admin-views"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent.parent / "templates"))

_GROUP_ORDER = ["site", "auth", "pbi", "feature", "i18n"]


@router.get(
    "/admin/config",
    response_class=HTMLResponse,
    dependencies=[require_permission("config.edit")],
)
async def config_page(
    request: Request,
    user: CurrentUser,
    tenant: CurrentTenant,
    db: DBSession,
    redis: RedisClient,
) -> HTMLResponse:
    result = await db.execute(
        select(SiteConfig).where(SiteConfig.tenant_id == tenant.id).order_by(SiteConfig.key)
    )
    configs = result.scalars().all()

    groups: dict[str, list] = {g: [] for g in _GROUP_ORDER}
    for cfg in configs:
        prefix = cfg.key.split(".")[0]
        groups.setdefault(prefix, []).append(cfg)
    groups = {k: v for k, v in groups.items() if v}

    config_values = {cfg.key: cfg.value for cfg in configs}
    ctx = await build_base_context(
        request, user, tenant, db, redis,
        extra={"config_groups": groups, "config_values": config_values},
    )
    return templates.TemplateResponse(request, "admin/config.html", ctx)
