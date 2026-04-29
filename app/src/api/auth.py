"""Authentication API endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import or_, select, update

from ..config import get_settings
from ..core import audit
from ..core.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_password_reset_token,
    hash_password,
    hash_token,
    verify_password,
)
from ..deps import CurrentUser, DBSession, RedisClient
from ..models.user import RefreshToken, User
from ..schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    ResetPasswordRequest,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
_settings = get_settings()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")


def _now() -> datetime:
    return datetime.now(timezone.utc)


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: DBSession,
    redis: RedisClient,
) -> LoginResponse:
    tenant_id = getattr(request.state, "tenant_id", None)

    # Lookup user by email, username, or id — within tenant scope
    stmt = select(User).where(
        User.tenant_id == tenant_id,
        or_(
            User.email == payload.identifier.lower().strip(),
            User.username == payload.identifier.strip(),
            User.id == payload.identifier.strip(),
        ),
    )
    result = await db.execute(stmt)
    user: User | None = result.scalar_one_or_none()

    ip = _client_ip(request)
    ua = request.headers.get("user-agent", "")[:512]

    async def _fail(reason: str) -> None:
        await audit.emit(
            db, action="login.fail", tenant_id=tenant_id,
            user_id=user.id if user else None,
            ip_address=ip, user_agent=ua,
            metadata={"reason": reason}, result="fail",
        )
        await db.commit()

    if not user or not user.is_active:
        await _fail("user_not_found")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")

    # Lockout check
    if user.locked_until and user.locked_until > _now():
        minutes_left = int((user.locked_until - _now()).total_seconds() / 60) + 1
        await _fail("account_locked")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "account_locked", "minutes": minutes_left},
        )

    if not verify_password(payload.password, user.password_hash):
        threshold = _settings.lockout_threshold
        new_attempts = user.failed_attempts + 1
        lock_until = None
        if new_attempts >= threshold:
            lock_until = _now() + timedelta(minutes=_settings.lockout_duration_min)
        await db.execute(
            update(User).where(User.id == user.id).values(
                failed_attempts=new_attempts, locked_until=lock_until
            )
        )
        await _fail("wrong_password")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")

    # Success — reset counters
    await db.execute(
        update(User).where(User.id == user.id).values(
            failed_attempts=0, locked_until=None, last_login_at=_now()
        )
    )

    two_fa_required = user.two_fa_enabled

    if not two_fa_required:
        # Issue tokens immediately
        jti = str(uuid.uuid4())
        access_token = create_access_token({
            "sub": user.id,
            "tenant_id": user.tenant_id,
            "jti": jti,
        })
        raw_refresh = create_refresh_token()
        rt = RefreshToken(
            user_id=user.id,
            token_hash=hash_token(raw_refresh),
            expires_at=_now() + timedelta(days=_settings.refresh_token_ttl_days),
            user_agent=ua,
            ip_address=ip,
        )
        db.add(rt)

        # Set cookies
        secure = _settings.is_production
        response.set_cookie(
            "access_token", access_token,
            httponly=True, secure=secure, samesite="strict",
            max_age=_settings.access_token_ttl_min * 60,
        )
        ttl = _settings.refresh_token_ttl_days * 86400 if payload.remember_me else None
        response.set_cookie(
            "refresh_token", raw_refresh,
            httponly=True, secure=secure, samesite="strict",
            max_age=ttl,
        )

    await audit.emit(
        db, action="login.success", tenant_id=tenant_id,
        user_id=user.id, ip_address=ip, user_agent=ua,
    )
    await db.commit()

    return LoginResponse(
        user_id=user.id,
        name=user.name,
        email=user.email,
        is_super_admin=user.is_super_admin,
        tenant_id=user.tenant_id,
        must_reset_pw=user.must_reset_pw,
        two_fa_required=two_fa_required,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: DBSession,
    redis: RedisClient,
    user: CurrentUser,
) -> None:
    ip = _client_ip(request)
    access_token = request.cookies.get("access_token")
    if access_token:
        from ..core.security import decode_access_token
        from jose import JWTError
        try:
            payload = decode_access_token(access_token)
            jti = payload.get("jti")
            if jti:
                ttl = _settings.access_token_ttl_min * 60
                await redis.setex(f"bl:jti:{jti}", ttl, "1")
        except JWTError:
            pass

    raw_refresh = request.cookies.get("refresh_token")
    if raw_refresh:
        token_hash = hash_token(raw_refresh)
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .values(revoked_at=_now())
        )

    await audit.emit(
        db, action="logout", tenant_id=user.tenant_id,
        user_id=user.id, ip_address=ip,
    )
    await db.commit()

    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")


@router.post("/refresh")
async def refresh_token(
    request: Request,
    response: Response,
    db: DBSession,
) -> dict[str, str]:
    raw_refresh = request.cookies.get("refresh_token")
    if not raw_refresh:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="no_refresh_token")

    token_hash = hash_token(raw_refresh)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > _now(),
        )
    )
    rt: RefreshToken | None = result.scalar_one_or_none()
    if not rt:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_refresh_token")

    # Rotate: revoke old, issue new
    await db.execute(
        update(RefreshToken).where(RefreshToken.id == rt.id).values(revoked_at=_now())
    )

    user_result = await db.execute(select(User).where(User.id == rt.user_id))
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user_inactive")

    jti = str(uuid.uuid4())
    new_access = create_access_token({"sub": user.id, "tenant_id": user.tenant_id, "jti": jti})
    new_raw_refresh = create_refresh_token()
    new_rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(new_raw_refresh),
        expires_at=rt.expires_at,  # keep original expiry
        user_agent=rt.user_agent,
        ip_address=rt.ip_address,
    )
    db.add(new_rt)
    await db.commit()

    secure = _settings.is_production
    response.set_cookie("access_token", new_access, httponly=True, secure=secure, samesite="strict",
                        max_age=_settings.access_token_ttl_min * 60)
    response.set_cookie("refresh_token", new_raw_refresh, httponly=True, secure=secure, samesite="strict")

    return {"status": "ok"}


@router.post("/forgot", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(payload: ForgotPasswordRequest, request: Request, db: DBSession) -> dict[str, str]:
    tenant_id = getattr(request.state, "tenant_id", None)
    result = await db.execute(
        select(User).where(User.email == payload.email.lower(), User.tenant_id == tenant_id)
    )
    user = result.scalar_one_or_none()
    if user:
        token = create_password_reset_token(user.id)
        reset_url = f"{_settings.app_base_url}/reset-password?token={token}"
        # TODO Phase 7: send email
        import structlog
        structlog.get_logger().info("password.reset_link", url=reset_url, user_id=user.id)
    return {"status": "email_sent_if_exists"}


@router.post("/reset")
async def reset_password(payload: ResetPasswordRequest, db: DBSession) -> dict[str, str]:
    from jose import JWTError
    try:
        user_id = decode_password_reset_token(payload.token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_token")

    await db.execute(
        update(User).where(User.id == user_id).values(
            password_hash=hash_password(payload.new_password),
            must_reset_pw=False,
            failed_attempts=0,
            locked_until=None,
        )
    )
    await db.commit()
    return {"status": "password_reset"}
