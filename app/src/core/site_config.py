"""Per-tenant site configuration loader with Redis cache."""
from __future__ import annotations

import colorsys
import json
from typing import Any

import structlog
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.config import DEFAULT_SITE_CONFIGS, SiteConfig

log = structlog.get_logger()
_TTL = 300  # 5 minutes


def _cache_key(tenant_id: str) -> str:
    return f"site_cfg:{tenant_id}"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb_str(r: int, g: int, b: int) -> str:
    return f"{r} {g} {b}"


def _generate_palette(primary_hex: str) -> dict[str, str]:
    """Return {shade_name: 'R G B'} for all Tailwind primary shades."""
    try:
        r, g, b = _hex_to_rgb(primary_hex)
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)

        def _shade(ns: float, nv: float) -> str:
            nr, ng, nb = colorsys.hsv_to_rgb(h, max(0, min(1, ns)), max(0, min(1, nv)))
            return _rgb_str(int(nr * 255), int(ng * 255), int(nb * 255))

        base = _rgb_str(r, g, b)
        return {
            "primary":     base,
            "primary_50":  _shade(s * 0.12, min(1.0, v * 1.5 + 0.42)),
            "primary_100": _shade(s * 0.22, min(1.0, v * 1.3 + 0.28)),
            "primary_500": base,
            "primary_600": _shade(min(1, s * 1.05), v * 0.87),
            "primary_700": _shade(min(1, s * 1.08), v * 0.72),
            "primary_900": _shade(min(1, s * 1.12), v * 0.50),
        }
    except Exception:
        return {
            "primary":     "14 165 233",
            "primary_50":  "240 249 255",
            "primary_100": "224 242 254",
            "primary_500": "14 165 233",
            "primary_600": "2 132 199",
            "primary_700": "3 105 161",
            "primary_900": "12 74 110",
        }


async def get_site_config(tenant_id: str, db: AsyncSession, redis: Redis) -> dict[str, Any]:
    """Load site config for a tenant; caches in Redis for 5 minutes."""
    raw = await redis.get(_cache_key(tenant_id))
    if raw:
        return json.loads(raw)

    result = await db.execute(
        select(SiteConfig).where(SiteConfig.tenant_id == tenant_id)
    )
    db_rows = result.scalars().all()

    cfg: dict[str, Any] = {d["key"]: d["value"] for d in DEFAULT_SITE_CONFIGS}
    for row in db_rows:
        cfg[row.key] = row.value

    primary_hex = str(cfg.get("site.primary_color") or "#0ea5e9")
    secondary_hex = str(cfg.get("site.secondary_color") or "#1e293b")

    cfg["_palette"] = _generate_palette(primary_hex)
    cfg["_secondary_rgb"] = _rgb_str(*_hex_to_rgb(secondary_hex))
    cfg["_brand_primary"] = primary_hex if primary_hex.startswith("#") else f"#{primary_hex}"
    cfg["_brand_secondary"] = secondary_hex if secondary_hex.startswith("#") else f"#{secondary_hex}"

    await redis.setex(_cache_key(tenant_id), _TTL, json.dumps(cfg))
    log.debug("site_config.loaded_from_db", tenant_id=tenant_id)
    return cfg


async def invalidate_cache(tenant_id: str, redis: Redis) -> None:
    await redis.delete(_cache_key(tenant_id))
    log.debug("site_config.cache_invalidated", tenant_id=tenant_id)
