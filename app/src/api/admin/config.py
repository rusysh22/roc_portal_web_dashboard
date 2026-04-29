"""Admin: Site configuration API."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ...core.audit import emit as audit_emit
from ...core.rbac import require_permission
from ...core.site_config import invalidate_cache as invalidate_site_config
from ...deps import CurrentTenant, CurrentUser, DBSession, RedisClient
from ...models.config import SiteConfig
from ...schemas.config import SiteConfigRead, SiteConfigUpdate

router = APIRouter(prefix="/api/admin/config", tags=["admin-config"])


@router.get("", response_model=list[SiteConfigRead], dependencies=[require_permission("config.edit")])
async def list_config(tenant: CurrentTenant, db: DBSession) -> list[SiteConfigRead]:
    result = await db.execute(
        select(SiteConfig).where(SiteConfig.tenant_id == tenant.id).order_by(SiteConfig.key)
    )
    return result.scalars().all()  # type: ignore[return-value]


@router.put("/{key}", dependencies=[require_permission("config.edit")])
async def update_config_key(
    key: str,
    body: SiteConfigUpdate,
    user: CurrentUser,
    tenant: CurrentTenant,
    db: DBSession,
    redis: RedisClient,
) -> dict:
    result = await db.execute(
        select(SiteConfig).where(SiteConfig.tenant_id == tenant.id, SiteConfig.key == key)
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=404, detail="config_key_not_found")

    cfg.value = body.value
    cfg.updated_at = datetime.now(timezone.utc)
    cfg.updated_by = user.id
    await db.commit()
    await audit_emit(
        db,
        user_id=user.id,
        tenant_id=tenant.id,
        action="update.config",
        target_type="config",
        target_id=key,
        metadata={"value": str(body.value)},
    )
    await invalidate_site_config(tenant.id, redis)
    return {"ok": True}
