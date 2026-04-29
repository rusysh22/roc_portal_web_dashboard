"""Admin: User CRUD endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ...core.audit import emit as audit_emit
from ...core.rbac import require_permission
from ...core.security import hash_password
from ...deps import CurrentTenant, CurrentUser, DBSession
from ...models.department import Department, UserDepartment
from ...models.user import Permission, Role, User, UserRole
from ...schemas.user import (
    PasswordResetByAdmin,
    UserCreate,
    UserListItem,
    UserListResponse,
    UserRead,
    UserUpdate,
)

router = APIRouter(prefix="/api/admin/users", tags=["admin-users"])


def _perm(code: str = "user.manage"):
    return require_permission(code)


@router.get("", response_model=UserListResponse, dependencies=[_perm()])
async def list_users(
    tenant: CurrentTenant,
    db: DBSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
) -> UserListResponse:
    base_q = (
        select(User)
        .where(User.tenant_id == tenant.id)
        .options(selectinload(User.roles).selectinload(Role.permissions), selectinload(User.departments))
    )
    if search:
        like = f"%{search}%"
        base_q = base_q.where(
            User.email.ilike(like) | User.name.ilike(like)
        )

    count_result = await db.execute(
        select(func.count()).select_from(base_q.subquery())
    )
    total = count_result.scalar_one()

    result = await db.execute(
        base_q.offset((page - 1) * page_size).limit(page_size).order_by(User.name)
    )
    users = result.scalars().all()
    return UserListResponse(
        items=[UserListItem.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED, dependencies=[_perm()])
async def create_user(
    body: UserCreate,
    tenant: CurrentTenant,
    actor: CurrentUser,
    db: DBSession,
) -> UserRead:
    # Check email unique in tenant
    existing = await db.execute(
        select(User).where(User.tenant_id == tenant.id, User.email == body.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="email_taken")

    new_user = User(
        tenant_id=tenant.id,
        email=body.email,
        name=body.name,
        username=body.username,
        password_hash=hash_password(body.password),
        is_active=body.is_active,
        must_reset_pw=body.must_reset_pw,
    )
    db.add(new_user)
    await db.flush()

    if body.role_ids:
        roles_result = await db.execute(
            select(Role).where(Role.tenant_id == tenant.id, Role.id.in_(body.role_ids))
        )
        for role in roles_result.scalars().all():
            db.add(UserRole(user_id=new_user.id, role_id=role.id))

    if body.department_ids:
        depts_result = await db.execute(
            select(Department).where(Department.tenant_id == tenant.id, Department.id.in_(body.department_ids))
        )
        for dept in depts_result.scalars().all():
            db.add(UserDepartment(user_id=new_user.id, department_id=dept.id))

    await db.commit()
    await db.refresh(new_user)

    result = await db.execute(
        select(User)
        .where(User.id == new_user.id)
        .options(selectinload(User.roles).selectinload(Role.permissions), selectinload(User.departments))
    )
    user = result.scalar_one()
    await audit_emit(db, user_id=actor.id, tenant_id=tenant.id, action="create.user", target_type="user", target_id=user.id, metadata={"email": user.email})
    return UserRead.model_validate(user)


@router.get("/{user_id}", response_model=UserRead, dependencies=[_perm()])
async def get_user(
    user_id: str,
    tenant: CurrentTenant,
    db: DBSession,
) -> UserRead:
    result = await db.execute(
        select(User)
        .where(User.id == user_id, User.tenant_id == tenant.id)
        .options(selectinload(User.roles).selectinload(Role.permissions))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")
    return UserRead.model_validate(user)


@router.put("/{user_id}", response_model=UserRead, dependencies=[_perm()])
async def update_user(
    user_id: str,
    body: UserUpdate,
    tenant: CurrentTenant,
    actor: CurrentUser,
    db: DBSession,
) -> UserRead:
    result = await db.execute(
        select(User)
        .where(User.id == user_id, User.tenant_id == tenant.id)
        .options(selectinload(User.roles))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    if body.name is not None:
        user.name = body.name
    if body.username is not None:
        user.username = body.username
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.must_reset_pw is not None:
        user.must_reset_pw = body.must_reset_pw

    from sqlalchemy import delete as sa_delete
    if body.role_ids is not None:
        await db.execute(sa_delete(UserRole).where(UserRole.user_id == user.id))
        if body.role_ids:
            roles_result = await db.execute(
                select(Role).where(Role.tenant_id == tenant.id, Role.id.in_(body.role_ids))
            )
            for role in roles_result.scalars().all():
                db.add(UserRole(user_id=user.id, role_id=role.id))

    if body.department_ids is not None:
        await db.execute(sa_delete(UserDepartment).where(UserDepartment.user_id == user.id))
        if body.department_ids:
            depts_result = await db.execute(
                select(Department).where(Department.tenant_id == tenant.id, Department.id.in_(body.department_ids))
            )
            for dept in depts_result.scalars().all():
                db.add(UserDepartment(user_id=user.id, department_id=dept.id))

    await db.commit()
    await audit_emit(db, user_id=actor.id, tenant_id=tenant.id, action="update.user", target_type="user", target_id=user.id)

    result2 = await db.execute(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.roles).selectinload(Role.permissions), selectinload(User.departments))
    )
    return UserRead.model_validate(result2.scalar_one())


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_perm()])
async def delete_user(
    user_id: str,
    tenant: CurrentTenant,
    actor: CurrentUser,
    db: DBSession,
) -> None:
    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == tenant.id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")
    if user.is_super_admin:
        raise HTTPException(status_code=400, detail="cannot_delete_super_admin")
    if user.id == actor.id:
        raise HTTPException(status_code=400, detail="cannot_delete_self")
    await audit_emit(db, user_id=actor.id, tenant_id=tenant.id, action="delete.user", target_type="user", target_id=user.id, metadata={"email": user.email})
    await db.delete(user)
    await db.commit()


@router.put("/{user_id}/password", dependencies=[_perm()])
async def reset_user_password(
    user_id: str,
    body: PasswordResetByAdmin,
    tenant: CurrentTenant,
    actor: CurrentUser,
    db: DBSession,
) -> dict:
    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == tenant.id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")
    user.password_hash = hash_password(body.new_password)
    user.must_reset_pw = True
    await db.commit()
    await audit_emit(db, user_id=actor.id, tenant_id=tenant.id, action="reset.password", target_type="user", target_id=user.id)
    return {"ok": True}
