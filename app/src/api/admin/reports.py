"""Admin: Report CRUD endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete as sa_delete, select
from sqlalchemy.orm import selectinload

from ...core.audit import emit as audit_emit
from ...core.rbac import require_permission
from ...deps import CurrentTenant, CurrentUser, DBSession
from ...models.department import Department
from ...models.report import Report, ReportDepartmentAccess, ReportRoleAccess, ReportUserAccess
from ...models.user import Role, User
from ...schemas.report import ReportCreate, ReportListItem, ReportRead, ReportUpdate

router = APIRouter(prefix="/api/admin/reports", tags=["admin-reports"])


def _perm():
    return require_permission("report.manage")


def _load_report_opts():
    return [
        selectinload(Report.roles),
        selectinload(Report.departments),
        selectinload(Report.users),
    ]


@router.get("", response_model=list[ReportListItem], dependencies=[_perm()])
async def list_reports(tenant: CurrentTenant, db: DBSession) -> list[ReportListItem]:
    result = await db.execute(
        select(Report)
        .where(Report.tenant_id == tenant.id)
        .options(*_load_report_opts())
        .order_by(Report.order_index, Report.name)
    )
    return [ReportListItem.model_validate(r) for r in result.scalars().all()]


@router.post("", response_model=ReportRead, status_code=status.HTTP_201_CREATED, dependencies=[_perm()])
async def create_report(
    body: ReportCreate,
    tenant: CurrentTenant,
    actor: CurrentUser,
    db: DBSession,
) -> ReportRead:
    existing = await db.execute(
        select(Report).where(Report.tenant_id == tenant.id, Report.slug == body.slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="slug_taken")

    report = Report(
        tenant_id=tenant.id,
        slug=body.slug,
        name=body.name,
        description=body.description,
        workspace_id=body.workspace_id,
        report_id=body.report_id,
        dataset_id=body.dataset_id,
        embed_type=body.embed_type,
        public_url=body.public_url,
        html_embed=body.html_embed,
        display_config=body.display_config,
        is_rls=body.is_rls,
        rls_config=body.rls_config,
        export_config=body.export_config,
        is_active=body.is_active,
        order_index=body.order_index,
    )
    db.add(report)
    await db.flush()

    await _sync_access(db, report.id, tenant.id, body.role_ids, body.department_ids, body.user_ids)

    await db.commit()
    await audit_emit(db, user_id=actor.id, tenant_id=tenant.id, action="create.report", target_type="report", target_id=report.id, metadata={"slug": report.slug})

    result = await db.execute(
        select(Report).where(Report.id == report.id).options(*_load_report_opts())
    )
    return ReportRead.model_validate(result.scalar_one())


@router.get("/{report_id}", response_model=ReportRead, dependencies=[_perm()])
async def get_report(report_id: str, tenant: CurrentTenant, db: DBSession) -> ReportRead:
    result = await db.execute(
        select(Report)
        .where(Report.id == report_id, Report.tenant_id == tenant.id)
        .options(*_load_report_opts())
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="report_not_found")
    return ReportRead.model_validate(report)


@router.put("/{report_id}", response_model=ReportRead, dependencies=[_perm()])
async def update_report(
    report_id: str,
    body: ReportUpdate,
    tenant: CurrentTenant,
    actor: CurrentUser,
    db: DBSession,
) -> ReportRead:
    result = await db.execute(
        select(Report).where(Report.id == report_id, Report.tenant_id == tenant.id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="report_not_found")

    for field in ("name", "description", "workspace_id", "report_id", "dataset_id",
                  "embed_type", "public_url", "html_embed", "display_config", "is_rls",
                  "rls_config", "export_config", "is_active", "order_index"):
        val = getattr(body, field, None)
        if val is not None:
            setattr(report, field, val)

    if body.role_ids is not None or body.department_ids is not None or body.user_ids is not None:
        await _sync_access(
            db, report.id, tenant.id,
            body.role_ids, body.department_ids, body.user_ids,
            replace=True,
        )

    await db.commit()
    await audit_emit(db, user_id=actor.id, tenant_id=tenant.id, action="update.report", target_type="report", target_id=report.id)

    result2 = await db.execute(
        select(Report).where(Report.id == report_id).options(*_load_report_opts())
    )
    return ReportRead.model_validate(result2.scalar_one())


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_perm()])
async def delete_report(
    report_id: str,
    tenant: CurrentTenant,
    actor: CurrentUser,
    db: DBSession,
) -> None:
    result = await db.execute(
        select(Report).where(Report.id == report_id, Report.tenant_id == tenant.id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="report_not_found")
    await audit_emit(db, user_id=actor.id, tenant_id=tenant.id, action="delete.report", target_type="report", target_id=report.id, metadata={"slug": report.slug})
    await db.delete(report)
    await db.commit()


async def _sync_access(
    db,
    report_id: str,
    tenant_id: str,
    role_ids: list[str] | None,
    dept_ids: list[str] | None,
    user_ids: list[str] | None,
    replace: bool = False,
) -> None:
    if role_ids is not None:
        if replace:
            await db.execute(sa_delete(ReportRoleAccess).where(ReportRoleAccess.report_id == report_id))
        if role_ids:
            roles = (await db.execute(select(Role).where(Role.tenant_id == tenant_id, Role.id.in_(role_ids)))).scalars().all()
            for r in roles:
                db.add(ReportRoleAccess(report_id=report_id, role_id=r.id))

    if dept_ids is not None:
        if replace:
            await db.execute(sa_delete(ReportDepartmentAccess).where(ReportDepartmentAccess.report_id == report_id))
        if dept_ids:
            depts = (await db.execute(select(Department).where(Department.tenant_id == tenant_id, Department.id.in_(dept_ids)))).scalars().all()
            for d in depts:
                db.add(ReportDepartmentAccess(report_id=report_id, department_id=d.id))

    if user_ids is not None:
        if replace:
            await db.execute(sa_delete(ReportUserAccess).where(ReportUserAccess.report_id == report_id))
        if user_ids:
            users = (await db.execute(select(User).where(User.tenant_id == tenant_id, User.id.in_(user_ids)))).scalars().all()
            for u in users:
                db.add(ReportUserAccess(report_id=report_id, user_id=u.id))
