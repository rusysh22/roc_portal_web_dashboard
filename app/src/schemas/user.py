"""User request/response schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator


class UserCreate(BaseModel):
    email: EmailStr
    name: str
    username: str | None = None
    password: str
    is_active: bool = True
    must_reset_pw: bool = True
    role_ids: list[str] = []
    department_ids: list[str] = []

    @field_validator("password")
    @classmethod
    def strong_enough(cls, v: str) -> str:
        if len(v) < 12:
            raise ValueError("password_too_short")
        if not any(c.isupper() for c in v):
            raise ValueError("password_needs_upper")
        if not any(c.islower() for c in v):
            raise ValueError("password_needs_lower")
        if not any(c.isdigit() for c in v):
            raise ValueError("password_needs_digit")
        return v


class UserUpdate(BaseModel):
    name: str | None = None
    username: str | None = None
    is_active: bool | None = None
    must_reset_pw: bool | None = None
    role_ids: list[str] | None = None
    department_ids: list[str] | None = None


class PasswordResetByAdmin(BaseModel):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def strong_enough(cls, v: str) -> str:
        if len(v) < 12:
            raise ValueError("password_too_short")
        if not any(c.isupper() for c in v):
            raise ValueError("password_needs_upper")
        if not any(c.islower() for c in v):
            raise ValueError("password_needs_lower")
        if not any(c.isdigit() for c in v):
            raise ValueError("password_needs_digit")
        return v


class PasswordChange(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def strong_enough(cls, v: str) -> str:
        if len(v) < 12:
            raise ValueError("password_too_short")
        if not any(c.isupper() for c in v):
            raise ValueError("password_needs_upper")
        if not any(c.islower() for c in v):
            raise ValueError("password_needs_lower")
        if not any(c.isdigit() for c in v):
            raise ValueError("password_needs_digit")
        return v


class RoleRef(BaseModel):
    id: str
    name: str

    model_config = {"from_attributes": True}


class DeptRef(BaseModel):
    id: str
    name: str

    model_config = {"from_attributes": True}


class UserRead(BaseModel):
    id: str
    email: str
    name: str
    username: str | None
    is_active: bool
    is_super_admin: bool
    must_reset_pw: bool
    two_fa_enabled: bool
    last_login_at: datetime | None
    tenant_id: str
    roles: list[RoleRef] = []
    departments: list[DeptRef] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class UserListItem(BaseModel):
    id: str
    email: str
    name: str
    username: str | None
    is_active: bool
    is_super_admin: bool
    last_login_at: datetime | None
    roles: list[RoleRef] = []

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    items: list[UserListItem]
    total: int
    page: int
    page_size: int
