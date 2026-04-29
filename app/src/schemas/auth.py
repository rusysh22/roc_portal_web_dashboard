"""Auth request/response schemas."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, field_validator


class LoginRequest(BaseModel):
    identifier: str  # email, username, or user ID
    password: str
    remember_me: bool = False


class LoginResponse(BaseModel):
    user_id: str
    name: str
    email: str
    is_super_admin: bool
    tenant_id: str
    must_reset_pw: bool
    two_fa_required: bool


class RefreshRequest(BaseModel):
    pass  # token comes from httpOnly cookie


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
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


class TwoFAVerifyRequest(BaseModel):
    code: str
