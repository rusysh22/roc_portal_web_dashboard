"""Shared helper: load accessible nav reports for sidebar."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.report import Report


async def get_nav_reports(tenant_id: str, user, db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(Report)
        .where(Report.tenant_id == tenant_id, Report.is_active == True)
        .options(
            selectinload(Report.roles),
            selectinload(Report.departments),
            selectinload(Report.users),
        )
        .order_by(Report.order_index, Report.name)
    )
    reports = result.scalars().all()

    if user.is_super_admin:
        return [{"slug": r.slug, "name": r.name} for r in reports]

    role_ids = {r.id for r in user.roles}
    dept_ids = {d.id for d in user.departments}

    accessible = []
    for r in reports:
        if not r.roles and not r.departments and not r.users:
            accessible.append(r)
        elif any(u.id == user.id for u in r.users):
            accessible.append(r)
        elif r.roles and bool({role.id for role in r.roles} & role_ids):
            accessible.append(r)
        elif r.departments and bool({d.id for d in r.departments} & dept_ids):
            accessible.append(r)

    return [{"slug": r.slug, "name": r.name} for r in accessible]
