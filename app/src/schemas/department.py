"""Department request/response schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DepartmentCreate(BaseModel):
    name: str
    description: str | None = None


class DepartmentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class UserRef(BaseModel):
    id: str
    name: str
    email: str

    model_config = {"from_attributes": True}


class DepartmentRead(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: str | None
    created_at: datetime
    users: list[UserRef] = []

    model_config = {"from_attributes": True}


class DepartmentListItem(BaseModel):
    id: str
    name: str
    description: str | None
    user_count: int = 0

    model_config = {"from_attributes": True}
