"""RBAC permission checking dependency and decorator."""
from __future__ import annotations

from fastapi import Depends, HTTPException, status

from ..deps import CurrentUser


def require_permission(code: str):
    """FastAPI dependency: raise 403 if user lacks the permission code."""
    async def _check(user: CurrentUser) -> None:  # type: ignore[type-arg]
        if user.is_super_admin:
            return
        perms = {p.code for role in user.roles for p in role.permissions}
        if code not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="access_denied")
    return Depends(_check)
