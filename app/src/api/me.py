"""Current-user endpoints: profile & menu."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..core.audit import emit as audit_emit
from ..core.rbac import require_permission
from ..core.security import hash_password, verify_password
from ..deps import CurrentTenant, CurrentUser, DBSession
from ..models.menu import MenuItem
from ..models.user import Permission, Role, User
from ..schemas.menu import MenuItemRead
from ..schemas.user import PasswordChange, UserRead

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("", response_model=UserRead)
async def get_profile(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


@router.put("/password")
async def change_password(
    body: PasswordChange,
    user: CurrentUser,
    db: DBSession,
) -> dict:
    if not verify_password(body.current_password, user.password_hash):
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="wrong_current_password")

    stmt = select(User).where(User.id == user.id)
    result = await db.execute(stmt)
    db_user = result.scalar_one()
    db_user.password_hash = hash_password(body.new_password)
    db_user.must_reset_pw = False
    await db.commit()
    await audit_emit(db, user_id=user.id, tenant_id=user.tenant_id, action="update.password", target_type="user", target_id=user.id)
    return {"ok": True}


@router.get("/menu", response_model=list[MenuItemRead])
async def get_menu(
    user: CurrentUser,
    tenant: CurrentTenant,
    db: DBSession,
) -> list[MenuItemRead]:
    user_perms: set[str] = set()
    if not user.is_super_admin:
        user_perms = {p.code for role in user.roles for p in role.permissions}

    result = await db.execute(
        select(MenuItem)
        .where(
            MenuItem.tenant_id == tenant.id,
            MenuItem.is_active == True,
            MenuItem.parent_id == None,
        )
        .options(selectinload(MenuItem.children))
        .order_by(MenuItem.order_index)
    )
    top_items = result.scalars().all()

    def _can_see(item: MenuItem) -> bool:
        if not item.required_permission:
            return True
        if user.is_super_admin:
            return True
        return item.required_permission in user_perms

    filtered: list[MenuItemRead] = []
    for item in top_items:
        if not _can_see(item):
            continue
        children = [
            MenuItemRead.model_validate(c)
            for c in sorted(item.children, key=lambda x: x.order_index)
            if c.is_active and _can_see(c)
        ]
        item_read = MenuItemRead.model_validate(item)
        item_read.children = children
        filtered.append(item_read)

    return filtered
