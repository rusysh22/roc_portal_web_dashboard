"""Admin: Permission list (read-only; permissions are seeded, not created via UI)."""
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from ...core.rbac import require_permission
from ...deps import DBSession
from ...models.user import Permission
from ...schemas.role import PermissionRead

router = APIRouter(prefix="/api/admin/permissions", tags=["admin-permissions"])


@router.get("", response_model=list[PermissionRead], dependencies=[require_permission("role.manage")])
async def list_permissions(db: DBSession) -> list[PermissionRead]:
    result = await db.execute(select(Permission).order_by(Permission.code))
    return [PermissionRead.model_validate(p) for p in result.scalars().all()]
