"""User-facing report endpoints: list accessible reports + get embed config."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..core.powerbi import PowerBIError, get_embed_config
from ..core.rbac import require_permission
from ..deps import CurrentTenant, CurrentUser, DBSession, RedisClient
from ..models.report import Report
from ..models.user import Role
from ..schemas.report import ReportListItem

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _can_access(report: Report, user) -> bool:
    """Check if user can access the report based on roles, departments, or direct access."""
    if user.is_super_admin:
        return True
    if not report.roles and not report.departments and not report.users:
        return True
    if any(u.id == user.id for u in report.users):
        return True
    user_role_ids = {r.id for r in user.roles}
    if report.roles and bool({role.id for role in report.roles} & user_role_ids):
        return True
    user_dept_ids = {d.id for d in user.departments}
    if report.departments and bool({d.id for d in report.departments} & user_dept_ids):
        return True
    return False


def _report_opts():
    return [
        selectinload(Report.roles),
        selectinload(Report.departments),
        selectinload(Report.users),
    ]


@router.get("", response_model=list[ReportListItem], dependencies=[require_permission("report.view")])
async def list_reports(
    user: CurrentUser,
    tenant: CurrentTenant,
    db: DBSession,
) -> list[ReportListItem]:
    result = await db.execute(
        select(Report)
        .where(Report.tenant_id == tenant.id, Report.is_active == True)
        .options(*_report_opts())
        .order_by(Report.order_index, Report.name)
    )
    reports = result.scalars().all()
    return [ReportListItem.model_validate(r) for r in reports if _can_access(r, user)]


@router.get("/{slug}/embed", dependencies=[require_permission("report.view")])
async def get_embed(
    slug: str,
    user: CurrentUser,
    tenant: CurrentTenant,
    db: DBSession,
    redis: RedisClient,
) -> dict:
    """
    Returns embed configuration via authenticated XHR.
    Token/URL never appear in server-rendered HTML.
    """
    result = await db.execute(
        select(Report)
        .where(Report.slug == slug, Report.tenant_id == tenant.id, Report.is_active == True)
        .options(*_report_opts())
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="report_not_found")

    if not _can_access(report, user):
        raise HTTPException(status_code=403, detail="report_access_denied")

    # ── HTML embed path ───────────────────────────────────────────────────────
    if report.embed_type == "HTML":
        if not report.html_embed:
            raise HTTPException(status_code=500, detail="html_embed_not_set")
        return {
            "embed_type": "HTML",
            "html_embed": report.html_embed,
            "embed_url": None,
            "access_token": None,
            "token_expires_utc": None,
            "display_config": report.display_config,
            "report_name": report.name,
            "export_config": report.export_config,
        }

    # ── PublicUrl path: no SP token needed ───────────────────────────────────
    if report.embed_type == "PublicUrl":
        if not report.public_url:
            raise HTTPException(status_code=500, detail="public_url_not_set")
        return {
            "embed_type": "PublicUrl",
            "embed_url": report.public_url,
            "html_embed": None,
            "access_token": None,
            "token_expires_utc": None,
            "display_config": report.display_config,
            "report_name": report.name,
            "export_config": report.export_config,
        }

    # ── SP-based embed path ───────────────────────────────────────────────────
    rls_role: str | None = None
    if report.is_rls:
        role_mapping: dict = report.rls_config.get("role_mapping", {})
        user_role_names = {r.name for r in user.roles}
        for portal_role, pbi_role in role_mapping.items():
            if portal_role in user_role_names:
                rls_role = pbi_role
                break

    try:
        embed = await get_embed_config(
            workspace_id=report.workspace_id,
            report_id=report.report_id,
            dataset_id=report.dataset_id,
            embed_type=report.embed_type,
            is_rls=report.is_rls,
            rls_role=rls_role,
            username=user.email,
            redis=redis,
        )
    except PowerBIError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return {
        "embed_type": report.embed_type,
        "embed_url": embed["embed_url"],
        "html_embed": None,
        "access_token": embed["access_token"],
        "token_expires_utc": embed["token_expires_utc"],
        "display_config": report.display_config,
        "report_name": report.name,
        "export_config": report.export_config,
    }
