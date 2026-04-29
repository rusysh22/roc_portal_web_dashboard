"""Report schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReportCreate(BaseModel):
    slug: str
    name: str
    description: str | None = None
    workspace_id: str = ""
    report_id: str = ""
    dataset_id: str | None = None
    embed_type: str = "Report"
    public_url: str | None = None
    html_embed: str | None = None
    display_config: dict = {}
    is_rls: bool = False
    rls_config: dict = {}
    export_config: dict = {}
    is_active: bool = True
    order_index: int = 0
    role_ids: list[str] = []
    department_ids: list[str] = []
    user_ids: list[str] = []


class ReportUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    workspace_id: str | None = None
    report_id: str | None = None
    dataset_id: str | None = None
    embed_type: str | None = None
    public_url: str | None = None
    html_embed: str | None = None
    display_config: dict | None = None
    is_rls: bool | None = None
    rls_config: dict | None = None
    export_config: dict | None = None
    is_active: bool | None = None
    order_index: int | None = None
    role_ids: list[str] | None = None
    department_ids: list[str] | None = None
    user_ids: list[str] | None = None


class ReportRoleRef(BaseModel):
    id: str
    name: str

    model_config = {"from_attributes": True}


class ReportDeptRef(BaseModel):
    id: str
    name: str

    model_config = {"from_attributes": True}


class ReportUserRef(BaseModel):
    id: str
    name: str
    email: str

    model_config = {"from_attributes": True}


class ReportRead(BaseModel):
    id: str
    slug: str
    name: str
    description: str | None
    workspace_id: str
    report_id: str
    dataset_id: str | None
    embed_type: str
    public_url: str | None
    html_embed: str | None
    display_config: dict
    is_rls: bool
    rls_config: dict
    export_config: dict
    is_active: bool
    order_index: int
    tenant_id: str
    roles: list[ReportRoleRef] = []
    departments: list[ReportDeptRef] = []
    users: list[ReportUserRef] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportListItem(BaseModel):
    id: str
    slug: str
    name: str
    description: str | None
    embed_type: str
    is_active: bool
    order_index: int
    roles: list[ReportRoleRef] = []
    departments: list[ReportDeptRef] = []
    users: list[ReportUserRef] = []

    model_config = {"from_attributes": True}
