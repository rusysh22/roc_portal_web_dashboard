"""Shared view context builders — eliminates duplication across all view handlers."""
from __future__ import annotations

from typing import Any

from fastapi import Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security import generate_csrf_token
from ..core.site_config import get_site_config
from ..i18n import detect_locale, translate
from ._nav import get_nav_reports


def _locale(request: Request, tenant: Any = None) -> str:
    return detect_locale(
        cookie_lang=request.cookies.get("lang"),
        accept_language=request.headers.get("accept-language"),
        tenant_default=getattr(tenant, "default_locale", None),
    )


async def build_base_context(
    request: Request,
    user: Any,
    tenant: Any,
    db: AsyncSession,
    redis: Redis,
    *,
    extra: dict | None = None,
) -> dict:
    """Full context for all authenticated pages (layout.html extends base.html)."""
    locale = _locale(request, tenant)
    user_perms: set[str] = set()
    if not user.is_super_admin:
        user_perms = {p.code for role in user.roles for p in role.permissions}

    nav_reports = await get_nav_reports(tenant.id, user, db)
    site_cfg = await get_site_config(tenant.id, db, redis)
    app_name = str(site_cfg.get("site.name") or (tenant.name if tenant else "ROC Portal"))

    ctx: dict = {
        "t": lambda key, **kw: translate(key, locale=locale, **kw),
        "locale": locale,
        "tenant": tenant,
        "app_name": app_name,
        "current_user": user,
        "user_perms": user_perms,
        "nav_reports": nav_reports,
        "csrf_token": generate_csrf_token(),
        "site_config": site_cfg,
        "flash_success": request.query_params.get("success"),
        "flash_error": request.query_params.get("error"),
    }
    if extra:
        ctx.update(extra)
    return ctx


async def build_auth_context(
    request: Request,
    tenant: Any,
    db: AsyncSession,
    redis: Redis,
    *,
    extra: dict | None = None,
) -> dict:
    """Minimal context for unauthenticated pages (login, forgot-password, etc.)."""
    locale = _locale(request, tenant)
    site_cfg = await get_site_config(tenant.id, db, redis) if tenant else {}
    app_name = str(site_cfg.get("site.name") or (tenant.name if tenant else "ROC Portal"))

    ctx: dict = {
        "t": lambda key, **kw: translate(key, locale=locale, **kw),
        "locale": locale,
        "tenant": tenant,
        "app_name": app_name,
        "site_config": site_cfg,
    }
    if extra:
        ctx.update(extra)
    return ctx
