"""Admin: Role CRUD endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ...core.audit import emit as audit_emit
from ...core.rbac import require_permission
from ...deps import CurrentTenant, CurrentUser, DBSession
from ...models.user import Permission, Role, RolePermission
from ...schemas.role import RoleCreate, RoleListItem, RoleRead, RoleUpdate

router = APIRouter(prefix="/api/admin/roles", tags=["admin-roles"])


def _perm(code: str = "role.manage"):
    return require_permission(code)


@router.get("", response_model=list[RoleListItem], dependencies=[_perm()])
async def list_roles(tenant: CurrentTenant, db: DBSession) -> list[RoleListItem]:
    result = await db.execute(
        select(Role)
        .where(Role.tenant_id == tenant.id)
        .options(selectinload(Role.permissions))
        .order_by(Role.name)
    )
    return [RoleListItem.model_validate(r) for r in result.scalars().all()]


@router.post("", response_model=RoleRead, status_code=status.HTTP_201_CREATED, dependencies=[_perm()])
async def create_role(
    body: RoleCreate,
    tenant: CurrentTenant,
    actor: CurrentUser,
    db: DBSession,
) -> RoleRead:
    existing = await db.execute(
        select(Role).where(Role.tenant_id == tenant.id, Role.name == body.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="role_name_taken")

    role = Role(tenant_id=tenant.id, name=body.name, description=body.description)
    db.add(role)
    await db.flush()

    if body.permission_ids:
        perms_result = await db.execute(
            select(Permission).where(Permission.id.in_(body.permission_ids))
        )
        for perm in perms_result.scalars().all():
            db.add(RolePermission(role_id=role.id, permission_id=perm.id))

    await db.commit()
    await audit_emit(db, user_id=actor.id, tenant_id=tenant.id, action="create.role", target_type="role", target_id=role.id, metadata={"name": role.name})

    result = await db.execute(
        select(Role)
        .where(Role.id == role.id)
        .options(selectinload(Role.permissions))
    )
    return RoleRead.model_validate(result.scalar_one())


@router.get("/{role_id}", response_model=RoleRead, dependencies=[_perm()])
async def get_role(role_id: str, tenant: CurrentTenant, db: DBSession) -> RoleRead:
    result = await db.execute(
        select(Role)
        .where(Role.id == role_id, Role.tenant_id == tenant.id)
        .options(selectinload(Role.permissions))
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="role_not_found")
    return RoleRead.model_validate(role)


@router.put("/{role_id}", response_model=RoleRead, dependencies=[_perm()])
async def update_role(
    role_id: str,
    body: RoleUpdate,
    tenant: CurrentTenant,
    actor: CurrentUser,
    db: DBSession,
) -> RoleRead:
    result = await db.execute(
        select(Role)
        .where(Role.id == role_id, Role.tenant_id == tenant.id)
        .options(selectinload(Role.permissions))
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="role_not_found")
    if role.is_system:
        raise HTTPException(status_code=400, detail="cannot_edit_system_role")

    if body.name is not None:
        role.name = body.name
    if body.description is not None:
        role.description = body.description

    if body.permission_ids is not None:
        from sqlalchemy import delete
        await db.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
        if body.permission_ids:
            perms_result = await db.execute(
                select(Permission).where(Permission.id.in_(body.permission_ids))
            )
            for perm in perms_result.scalars().all():
                db.add(RolePermission(role_id=role.id, permission_id=perm.id))

    await db.commit()
    await audit_emit(db, user_id=actor.id, tenant_id=tenant.id, action="update.role", target_type="role", target_id=role.id)

    result2 = await db.execute(
        select(Role)
        .where(Role.id == role_id)
        .options(selectinload(Role.permissions))
    )
    return RoleRead.model_validate(result2.scalar_one())


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_perm()])
async def delete_role(
    role_id: str,
    tenant: CurrentTenant,
    actor: CurrentUser,
    db: DBSession,
) -> None:
    result = await db.execute(
        select(Role).where(Role.id == role_id, Role.tenant_id == tenant.id)
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="role_not_found")
    if role.is_system:
        raise HTTPException(status_code=400, detail="cannot_delete_system_role")
    await audit_emit(db, user_id=actor.id, tenant_id=tenant.id, action="delete.role", target_type="role", target_id=role.id, metadata={"name": role.name})
    await db.delete(role)
    await db.commit()
