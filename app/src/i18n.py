"""Lightweight i18n: load JSON catalogs and resolve dotted keys."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import get_settings

LOCALES_DIR = Path(__file__).parent / "locales"


@lru_cache(maxsize=8)
def _load_catalog(locale: str) -> dict[str, Any]:
    path = LOCALES_DIR / f"{locale}.json"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _resolve(catalog: dict[str, Any], key: str) -> str | None:
    node: Any = catalog
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node if isinstance(node, str) else None


def translate(key: str, locale: str | None = None, **kwargs: Any) -> str:
    """Translate a dotted key. Falls back to default locale, then to the key itself."""
    settings = get_settings()
    locale = locale or settings.app_default_locale
    value = _resolve(_load_catalog(locale), key)
    if value is None and locale != settings.app_default_locale:
        value = _resolve(_load_catalog(settings.app_default_locale), key)
    if value is None:
        return key
    if kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, IndexError):
            return value
    return value


def detect_locale(
    cookie_lang: str | None,
    accept_language: str | None,
    tenant_default: str | None = None,
) -> str:
    settings = get_settings()
    supported = settings.supported_locales_list
    if cookie_lang and cookie_lang in supported:
        return cookie_lang
    if accept_language:
        for part in accept_language.split(","):
            code = part.split(";")[0].strip().split("-")[0].lower()
            if code in supported:
                return code
    if tenant_default and tenant_default in supported:
        return tenant_default
    return settings.app_default_locale
