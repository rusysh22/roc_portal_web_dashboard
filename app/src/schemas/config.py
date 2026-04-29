"""SiteConfig schemas."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SiteConfigRead(BaseModel):
    key: str
    value: Any
    value_type: str
    description: str | None

    model_config = {"from_attributes": True}


class SiteConfigUpdate(BaseModel):
    value: Any
