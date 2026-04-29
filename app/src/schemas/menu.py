"""MenuItem schemas."""
from __future__ import annotations

from pydantic import BaseModel


class MenuItemCreate(BaseModel):
    parent_id: str | None = None
    label_key: str
    label_override: str | None = None
    icon: str | None = None
    url: str | None = None
    report_slug: str | None = None
    required_permission: str | None = None
    order_index: int = 0
    is_active: bool = True
    open_in_new_tab: bool = False


class MenuItemUpdate(BaseModel):
    parent_id: str | None = None
    label_key: str | None = None
    label_override: str | None = None
    icon: str | None = None
    url: str | None = None
    report_slug: str | None = None
    required_permission: str | None = None
    order_index: int | None = None
    is_active: bool | None = None
    open_in_new_tab: bool | None = None


class MenuItemRead(BaseModel):
    id: str
    parent_id: str | None
    label_key: str
    label_override: str | None
    icon: str | None
    url: str | None
    report_slug: str | None
    required_permission: str | None
    order_index: int
    is_active: bool
    open_in_new_tab: bool
    children: list["MenuItemRead"] = []

    model_config = {"from_attributes": True}
