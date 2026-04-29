"""User-facing report endpoints: list accessible reports + get embed config."""
from __future__ import annotations

import json
import os
import re
from base64 import b64encode

import httpx
import structlog
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..core.powerbi import PowerBIError, get_embed_config
from ..core.rbac import require_permission
from ..deps import CurrentTenant, CurrentUser, DBSession, RedisClient
from ..models.report import Report
from ..models.user import Role
from ..schemas.report import ReportListItem

log = structlog.get_logger()

router = APIRouter(prefix="/api/reports", tags=["reports"])

_PBI_BASE = "https://app.powerbi.com"

# Obfuscated field names for the embed config XHR response.
# The real field names never appear in the Network tab payload.
# Frontend must use the matching decode map (_F in report.html).
_F: dict[str, str] = {
    "embed_type":        "a3f9d2c7e1b84650",
    "embed_url":         "f7b1e5a9c3d20846",
    "html_embed":        "d4c8b2f6e0a71359",
    "access_token":      "e2a6f0d4c8b31975",
    "token_expires_utc": "b5e9a3d7f1c40268",
    "display_config":    "c1d5f9b3e7a60482",
    "report_name":       "f8a2e6c0d4b91573",
    "export_config":     "d0b4e8a2f6c51397",
}


_SEP = "::0xDEAD::"  # separator that cannot appear in base64


def _encode_val(v: object) -> str:
    """JSON-serialize a value, base64-encode it, then append separator + random hex noise."""
    raw = json.dumps(v, ensure_ascii=False)
    b64 = b64encode(raw.encode("utf-8")).decode()
    noise = os.urandom(8).hex()
    return f"{b64}{_SEP}{noise}"


def _obf(d: dict) -> dict:
    """Rename keys with obfuscation map and encode every value."""
    return {_F.get(k, k): _encode_val(v) for k, v in d.items()}


def _extract_iframe_src(html: str) -> str | None:
    """Extract src attribute from the first iframe tag in an HTML string."""
    m = re.search(r'<iframe[^>]+\bsrc=["\']([^"\']+)["\']', html, re.IGNORECASE)
    return m.group(1) if m else None


def _inject_base_tag(html: str) -> str:
    """Inject <base href="https://app.powerbi.com/"> right after <head> so that
    relative paths inside the proxied PBI page resolve correctly."""
    base = f'<base href="{_PBI_BASE}/">'
    lower = html.lower()
    if "<head>" in lower:
        pos = lower.index("<head>") + len("<head>")
        return html[:pos] + base + html[pos:]
    return base + html


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
        pbi_url = _extract_iframe_src(report.html_embed or "")
        if not pbi_url:
            raise HTTPException(status_code=500, detail="html_embed_not_set")
        # URL is sent obfuscated (base64 + noise) — never plain text in the response.
        return _obf({
            "embed_type": "HTML",
            "html_embed": None,
            "embed_url": pbi_url,
            "access_token": None,
            "token_expires_utc": None,
            "display_config": report.display_config,
            "report_name": report.name,
            "export_config": report.export_config,
        })

    # ── PublicUrl path: no SP token needed ───────────────────────────────────
    if report.embed_type == "PublicUrl":
        if not report.public_url:
            raise HTTPException(status_code=500, detail="public_url_not_set")
        # URL is sent obfuscated (base64 + noise) — never plain text in the response.
        return _obf({
            "embed_type": "PublicUrl",
            "embed_url": report.public_url,
            "html_embed": None,
            "access_token": None,
            "token_expires_utc": None,
            "display_config": report.display_config,
            "report_name": report.name,
            "export_config": report.export_config,
        })

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

    return _obf({
        "embed_type": report.embed_type,
        "embed_url": embed["embed_url"],
        "html_embed": None,
        "access_token": embed["access_token"],
        "token_expires_utc": embed["token_expires_utc"],
        "display_config": report.display_config,
        "report_name": report.name,
        "export_config": report.export_config,
    })


@router.get("/{slug}/view", dependencies=[require_permission("report.view")])
async def proxy_report_view(
    slug: str,
    user: CurrentUser,
    tenant: CurrentTenant,
    db: DBSession,
) -> HTMLResponse:
    """
    Fetch the Power BI public page server-side and return it to the client.

    The iframe in the browser points to this endpoint (/api/reports/{slug}/view),
    so the real app.powerbi.com URL never appears in Inspect Element or in the
    XHR response of the embed config endpoint.
    Only applies to HTML and PublicUrl embed types.
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

    pbi_url: str | None = None
    if report.embed_type == "HTML":
        pbi_url = _extract_iframe_src(report.html_embed or "")
    elif report.embed_type == "PublicUrl":
        pbi_url = report.public_url

    if not pbi_url:
        raise HTTPException(status_code=422, detail="proxy_url_unavailable")

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            pbi_resp = await client.get(
                pbi_url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; ROCPortal/1.0)"},
            )
        pbi_resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        log.error("pbi.proxy_http_error", slug=slug, status=exc.response.status_code)
        raise HTTPException(status_code=502, detail="proxy_upstream_error")
    except httpx.RequestError as exc:
        log.error("pbi.proxy_request_failed", slug=slug, error=str(exc))
        raise HTTPException(status_code=502, detail="proxy_fetch_failed")

    html = _inject_base_tag(pbi_resp.text)
    return HTMLResponse(
        content=html,
        headers={"Cache-Control": "no-store, no-cache"},
    )
