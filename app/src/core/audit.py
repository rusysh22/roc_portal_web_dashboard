"""Audit logging helper — fire-and-forget inside request context."""
from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.audit import AuditLog

log = structlog.get_logger()


async def emit(
    db: AsyncSession,
    *,
    action: str,
    tenant_id: str | None = None,
    user_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    result: str = "ok",
) -> None:
    entry = AuditLog(
        action=action,
        tenant_id=tenant_id,
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        target_type=target_type,
        target_id=target_id,
        extra=metadata or {},
        result=result,
    )
    db.add(entry)
    # Caller is responsible for commit; we don't commit here to allow batching
    log.info("audit", action=action, user_id=user_id, tenant_id=tenant_id, result=result)
