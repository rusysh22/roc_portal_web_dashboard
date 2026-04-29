"""FastAPI dependencies: database session, Redis, current user, current tenant."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Cookie, Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .config import get_settings
from .core.security import decode_access_token
from .db import get_db
from .models.tenant import Tenant
from .models.user import Permission, Role, User

_settings = get_settings()
_redis_pool: aioredis.ConnectionPool | None = None


def _get_redis_pool() -> aioredis.ConnectionPool:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.ConnectionPool.from_url(_settings.redis_url)
    return _redis_pool


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:  # type: ignore[type-arg]
    pool = _get_redis_pool()
    async with aioredis.Redis(connection_pool=pool) as r:
        yield r


DBSession = Annotated[AsyncSession, Depends(get_db)]
RedisClient = Annotated[aioredis.Redis, Depends(get_redis)]  # type: ignore[type-arg]


async def get_current_user(
    request: Request,
    db: DBSession,
    redis: RedisClient,
    access_token: Annotated[str | None, Cookie(alias="access_token")] = None,
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="not_authenticated",
    )
    if not access_token:
        raise credentials_exception
    try:
        payload = decode_access_token(access_token)
    except JWTError:
        raise credentials_exception

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise credentials_exception

    # Check token not blacklisted (logged out)
    jti: str | None = payload.get("jti")
    if jti and await redis.exists(f"bl:jti:{jti}"):
        raise credentials_exception

    from .models.department import Department
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.roles).selectinload(Role.permissions).selectinload(Permission.roles),
            selectinload(User.departments),
        )
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise credentials_exception

    tenant_id = getattr(request.state, "tenant_id", None)
    if tenant_id and not user.is_super_admin and user.tenant_id != tenant_id:
        raise credentials_exception

    return user


async def get_current_user_optional(
    request: Request,
    db: DBSession,
    redis: RedisClient,
    access_token: Annotated[str | None, Cookie(alias="access_token")] = None,
) -> User | None:
    if not access_token:
        return None
    try:
        return await get_current_user(request, db, redis, access_token)
    except HTTPException:
        return None


async def get_current_tenant(request: Request) -> Tenant:
    tenant = getattr(request.state, "tenant", None)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tenant_not_found")
    return tenant


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentUserOptional = Annotated[User | None, Depends(get_current_user_optional)]
CurrentTenant = Annotated[Tenant, Depends(get_current_tenant)]
