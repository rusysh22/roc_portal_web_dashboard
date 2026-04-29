"""Power BI Service Principal auth & embed token helper."""
from __future__ import annotations

import json
import time
from typing import Any

import httpx
import msal
import structlog
from redis.asyncio import Redis

from ..config import get_settings

log = structlog.get_logger()
_settings = get_settings()

# ── Redis cache keys ──────────────────────────────────────────────────────────
_AAD_KEY = "pbi:aad_token:global"


class PowerBIError(Exception):
    """Raised when PBI API returns an error."""


def _is_sp_configured() -> bool:
    s = _settings
    return bool(s.azure_tenant_id and s.azure_client_id and s.azure_client_secret)


# ── AAD token (cached in Redis) ───────────────────────────────────────────────

async def get_aad_token(redis: Redis) -> str:
    """Return a valid AAD access token for Power BI API, using Redis cache."""
    cached = await redis.get(_AAD_KEY)
    if cached:
        data = json.loads(cached)
        if data.get("expires_at", 0) > time.time() + 60:
            return data["access_token"]

    if not _is_sp_configured():
        raise PowerBIError("sp_not_configured")

    authority = f"{_settings.pbi_authority}/{_settings.azure_tenant_id}"
    app = msal.ConfidentialClientApplication(
        client_id=_settings.azure_client_id,
        client_credential=_settings.azure_client_secret,
        authority=authority,
    )
    result = app.acquire_token_for_client(scopes=[_settings.pbi_scope])

    if "access_token" not in result:
        err = result.get("error_description", result.get("error", "unknown"))
        log.error("pbi.aad_token_failed", error=err)
        raise PowerBIError(f"aad_token_failed: {err}")

    expires_in = int(result.get("expires_in", 3600))
    payload = {
        "access_token": result["access_token"],
        "expires_at": time.time() + expires_in,
    }
    await redis.setex(_AAD_KEY, expires_in - 30, json.dumps(payload))
    log.info("pbi.aad_token_refreshed")
    return result["access_token"]


# ── Embed token ───────────────────────────────────────────────────────────────

async def get_embed_config(
    *,
    workspace_id: str,
    report_id: str,
    dataset_id: str | None,
    embed_type: str,
    is_rls: bool,
    rls_role: str | None,
    username: str | None,
    redis: Redis,
) -> dict[str, Any]:
    """
    Call PBI REST API to:
    1. GET report embed URL
    2. POST /GenerateToken for an embed token

    Returns: { "embed_url": str, "access_token": str, "token_expires_utc": str }
    """
    aad_token = await get_aad_token(redis)
    headers = {"Authorization": f"Bearer {aad_token}", "Content-Type": "application/json"}
    base = _settings.pbi_api_base

    async with httpx.AsyncClient(timeout=15) as client:
        # 1. Get report info (embed URL)
        report_url = f"{base}/groups/{workspace_id}/reports/{report_id}"
        r = await client.get(report_url, headers=headers)
        if r.status_code != 200:
            log.error("pbi.get_report_failed", status=r.status_code, body=r.text[:200])
            raise PowerBIError(f"get_report_failed: {r.status_code}")
        report_info = r.json()
        embed_url = report_info.get("embedUrl", "")

        # 2. Generate embed token
        token_endpoint = f"{base}/groups/{workspace_id}/reports/{report_id}/GenerateToken"
        token_body: dict[str, Any] = {"accessLevel": "View"}

        if is_rls and rls_role and username:
            token_body["identities"] = [
                {
                    "username": username,
                    "roles": [rls_role],
                    "datasets": [dataset_id] if dataset_id else [],
                }
            ]

        t = await client.post(token_endpoint, headers=headers, json=token_body)
        if t.status_code != 200:
            log.error("pbi.generate_token_failed", status=t.status_code, body=t.text[:200])
            raise PowerBIError(f"generate_token_failed: {t.status_code}")

        token_data = t.json()
        return {
            "embed_url": embed_url,
            "access_token": token_data["token"],
            "token_expires_utc": token_data.get("expiration", ""),
        }
