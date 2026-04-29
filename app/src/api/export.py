"""Export API: trigger PDF/PPTX export via Power BI exportToFile."""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..core.powerbi import PowerBIError, get_aad_token
from ..core.rbac import require_permission
from ..deps import CurrentTenant, CurrentUser, DBSession, RedisClient
from ..models.report import Report

log = structlog.get_logger()
router = APIRouter(prefix="/api/exports", tags=["exports"])

_JOB_TTL = 3600  # 1 hour


class ExportRequest(BaseModel):
    format: str  # "pdf" | "pptx"


@router.post("/reports/{slug}", dependencies=[require_permission("report.export")])
async def start_export(
    slug: str,
    body: ExportRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUser,
    tenant: CurrentTenant,
    db: DBSession,
    redis: RedisClient,
) -> dict:
    if body.format not in ("pdf", "pptx"):
        raise HTTPException(status_code=400, detail="invalid_format")

    result = await db.execute(
        select(Report)
        .where(Report.slug == slug, Report.tenant_id == tenant.id, Report.is_active == True)
        .options(selectinload(Report.roles))
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="report_not_found")

    export_cfg: dict = report.export_config or {}
    if not export_cfg.get(f"{body.format}_allowed", False):
        raise HTTPException(status_code=403, detail="export_not_allowed_for_this_report")

    if report.embed_type == "PublicUrl":
        raise HTTPException(status_code=400, detail="export_not_supported_for_public_url")

    job_id = str(uuid.uuid4())
    job_data: dict[str, Any] = {
        "status": "queued",
        "format": body.format,
        "report_name": report.name,
        "slug": slug,
        "workspace_id": report.workspace_id,
        "report_id": report.report_id,
        "user_id": user.id,
        "created_at": time.time(),
    }
    await redis.setex(f"export_job:{job_id}", _JOB_TTL, json.dumps(job_data))

    background_tasks.add_task(
        _run_export,
        job_id=job_id,
        workspace_id=report.workspace_id,
        report_id=report.report_id,
        fmt=body.format,
        slug=slug,
        redis=redis,
    )
    return {"job_id": job_id}


@router.get("/{job_id}/status")
async def export_status(job_id: str, user: CurrentUser, redis: RedisClient) -> dict:
    raw = await redis.get(f"export_job:{job_id}")
    if not raw:
        raise HTTPException(status_code=404, detail="job_not_found")
    data: dict = json.loads(raw)
    if not user.is_super_admin and data.get("user_id") != user.id:
        raise HTTPException(status_code=403, detail="access_denied")
    return {k: v for k, v in data.items() if k not in ("workspace_id", "report_id", "user_id")}


@router.get("/{job_id}/download")
async def download_export(job_id: str, user: CurrentUser, redis: RedisClient) -> StreamingResponse:
    from ..config import get_settings
    settings = get_settings()

    raw = await redis.get(f"export_job:{job_id}")
    if not raw:
        raise HTTPException(status_code=404, detail="job_not_found")
    data: dict = json.loads(raw)

    if not user.is_super_admin and data.get("user_id") != user.id:
        raise HTTPException(status_code=403, detail="access_denied")
    if data.get("status") != "done":
        raise HTTPException(status_code=400, detail="export_not_ready")

    pbi_export_id = data.get("pbi_export_id")
    workspace_id = data.get("workspace_id")
    report_id = data.get("report_id")
    fmt = data.get("format", "pdf")

    aad_token = await get_aad_token(redis)
    file_url = (
        f"{settings.pbi_api_base}/groups/{workspace_id}"
        f"/reports/{report_id}/exports/{pbi_export_id}/file"
    )
    headers = {"Authorization": f"Bearer {aad_token}"}

    mime = (
        "application/pdf"
        if fmt == "pdf"
        else "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )
    filename = f"{data.get('slug', 'report')}.{fmt}"

    async def _stream():  # type: ignore[no-untyped-def]
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", file_url, headers=headers) as resp:
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    yield chunk

    return StreamingResponse(
        _stream(),
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def _run_export(
    *,
    job_id: str,
    workspace_id: str,
    report_id: str,
    fmt: str,
    slug: str,
    redis: Any,
) -> None:
    from ..config import get_settings
    settings = get_settings()
    job_key = f"export_job:{job_id}"

    async def _save(patch: dict) -> None:
        raw = await redis.get(job_key)
        data = json.loads(raw) if raw else {}
        data.update(patch)
        await redis.setex(job_key, _JOB_TTL, json.dumps(data))

    await _save({"status": "processing"})

    try:
        aad_token = await get_aad_token(redis)
        headers = {"Authorization": f"Bearer {aad_token}", "Content-Type": "application/json"}
        base = settings.pbi_api_base
        pbi_format = "PDF" if fmt == "pdf" else "PPTX"
        export_url = f"{base}/groups/{workspace_id}/reports/{report_id}/ExportTo"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(export_url, headers=headers, json={"format": pbi_format})
            if resp.status_code not in (200, 202):
                raise PowerBIError(f"export_start_failed: {resp.status_code}")

            pbi_export_id = resp.json().get("id")
            if not pbi_export_id:
                raise PowerBIError("export_id_missing")

            status_url = f"{base}/groups/{workspace_id}/reports/{report_id}/exports/{pbi_export_id}"
            for _ in range(60):
                await asyncio.sleep(10)
                poll = await client.get(status_url, headers=headers)
                if poll.status_code != 200:
                    raise PowerBIError(f"export_poll_failed: {poll.status_code}")
                pbi_status = poll.json().get("status", "")

                if pbi_status == "Succeeded":
                    await _save({
                        "status": "done",
                        "pbi_export_id": pbi_export_id,
                        "download_url": f"/api/exports/{job_id}/download",
                        "completed_at": time.time(),
                    })
                    log.info("export.done", job_id=job_id, slug=slug, format=fmt)
                    return

                if pbi_status in ("Failed", "Undefined"):
                    raise PowerBIError(f"pbi_export_failed: {pbi_status}")

            raise PowerBIError("export_timeout")

    except Exception as exc:
        log.error("export.error", job_id=job_id, error=str(exc))
        await _save({"status": "error", "error": str(exc)})
