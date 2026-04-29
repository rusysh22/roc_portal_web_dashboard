"""Role & Permission schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PermissionRead(BaseModel):
    id: str
    code: str
    description: str | None

    model_config = {"from_attributes": True}


class RoleCreate(BaseModel):
    name: str
    description: str | None = None
    permission_ids: list[str] = []


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    permission_ids: list[str] | None = None


class RoleRead(BaseModel):
    id: str
    name: str
    description: str | None
    is_system: bool
    tenant_id: str
    permissions: list[PermissionRead] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class RoleListItem(BaseModel):
    id: str
    name: str
    description: str | None
    is_system: bool
    permissions: list[PermissionRead] = []

    model_config = {"from_attributes": True}
