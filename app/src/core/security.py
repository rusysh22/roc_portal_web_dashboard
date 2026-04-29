"""JWT, password hashing, CSRF utilities."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from ..config import get_settings

_settings = get_settings()
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


# ── Password ──────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


# ── JWT ───────────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(payload: dict[str, Any]) -> str:
    data = payload.copy()
    data["exp"] = _now() + timedelta(minutes=_settings.access_token_ttl_min)
    data["iat"] = _now()
    data["type"] = "access"
    return jwt.encode(data, _settings.app_secret_key, algorithm=_settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Raises JWTError on invalid/expired tokens."""
    payload = jwt.decode(token, _settings.app_secret_key, algorithms=[_settings.jwt_algorithm])
    if payload.get("type") != "access":
        raise JWTError("wrong token type")
    return payload


def create_refresh_token() -> str:
    """Returns a random 48-char urlsafe token (stored hashed in DB)."""
    return secrets.token_urlsafe(48)


def hash_token(raw: str) -> str:
    """SHA-256 of a raw token for safe DB storage."""
    return hashlib.sha256(raw.encode()).hexdigest()


def create_password_reset_token(user_id: str) -> str:
    data = {
        "sub": user_id,
        "exp": _now() + timedelta(minutes=30),
        "type": "pw_reset",
    }
    return jwt.encode(data, _settings.app_secret_key, algorithm=_settings.jwt_algorithm)


def decode_password_reset_token(token: str) -> str:
    """Returns user_id or raises JWTError."""
    payload = jwt.decode(token, _settings.app_secret_key, algorithms=[_settings.jwt_algorithm])
    if payload.get("type") != "pw_reset":
        raise JWTError("wrong token type")
    return payload["sub"]


# ── CSRF ──────────────────────────────────────────────────────────────────────

def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def verify_csrf_token(cookie_token: str, header_token: str) -> bool:
    return hmac.compare_digest(cookie_token, header_token)
