"""Tenant resolver middleware — sets request.state.tenant."""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import AsyncSessionLocal
from ..models.tenant import Tenant

_settings = get_settings()


async def _resolve_tenant(request: Request) -> Tenant | None:
    slug: str | None = None

    if _settings.tenant_resolution == "subdomain":
        host = request.headers.get("host", "").split(":")[0].lower()
        base = _settings.tenant_base_domain.lower()
        if host != base and host.endswith("." + base):
            slug = host[: -(len(base) + 1)]
    elif _settings.tenant_resolution == "path":
        parts = request.url.path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "t":
            slug = parts[1]

    # Dev override via header
    if slug is None:
        slug = request.headers.get("x-tenant-slug")

    if slug is None:
        slug = _settings.default_tenant_slug

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Tenant).where(Tenant.slug == slug, Tenant.is_active == True)  # noqa: E712
        )
        return result.scalar_one_or_none()


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        # Skip tenant resolution for static files and healthz
        path = request.url.path
        if path.startswith("/static") or path == "/healthz":
            return await call_next(request)

        tenant = await _resolve_tenant(request)
        request.state.tenant = tenant
        request.state.tenant_id = tenant.id if tenant else None
        return await call_next(request)
