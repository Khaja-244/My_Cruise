"""Authentication, email verification, and password-management endpoints."""

from datetime import datetime, timedelta, timezone
import secrets

from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.deps import get_current_user
from app.core.exceptions import AppError
from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    hash_token,
    validate_password_strength,
    verify_password,
)
from app.models import OTPCode, OTTPurpose, RefreshToken, User
from app.schemas.auth import (
    ChangePasswordIn,
    ForgotIn,
    LoginIn,
    ProfilePatch,
    RegisterIn,
    ResetIn,
    TokenOut,
    UserOut,
    VerifyOTPIn,
    RefreshOut,
)
from app.services.auth_service import create_otp, login, register
from app.services.rate_limit_service import check_rate_limit

router = APIRouter(prefix="/auth", tags=["Authentication"])


def out(user: User) -> UserOut:
    """Convert the database user model into the public user response."""
    return UserOut(
        id=str(user.id),
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        role=user.role.value,
        is_email_verified=user.is_email_verified,
        must_change_password=user.must_change_password,
    )


def _refresh_cookie_options() -> dict:
    """Return the common secure settings for the refresh-token cookie."""
    return {
        "httponly": True,
        "secure": settings.APP_ENV != "development",
        "samesite": "lax",
        "max_age": settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        "path": "/",
    }


@router.post("/register", response_model=TokenOut)
async def reg(
    data: RegisterIn,
    response: Response,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Register a traveler and start email verification."""
    client_ip = request.client.host if request.client else "unknown"
    await check_rate_limit(session, f"register:ip:{client_ip}", 3, 3600)

    user = await register(
        session,
        data.email,
        data.full_name,
        data.password,
        data.phone,
    )
    user.is_email_verified = False

    await create_otp(session, user.email, OTTPurpose.email_verify)
    logged_in_user, access_token, refresh_token = await login(
        session,
        data.email,
        data.password,
    )

    response.set_cookie(
        "refresh_token",
        refresh_token,
        **_refresh_cookie_options(),
    )

    return TokenOut(
        access_token=access_token,
        user=out(logged_in_user),
    )


@router.post("/login", response_model=TokenOut)
async def log(
    data: LoginIn,
    response: Response,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Authenticate a user and issue access and refresh tokens."""
    client_ip = request.client.host if request.client else "unknown"

    await check_rate_limit(session, f"login:ip:{client_ip}", 5, 900)
    await check_rate_limit(
        session,
        f"login:email:{data.email.lower().strip()}",
        5,
        900,
    )

    user, access_token, refresh_token = await login(
        session,
        data.email,
        data.password,
    )

    response.set_cookie(
        "refresh_token",
        refresh_token,
        **_refresh_cookie_options(),
    )

    return TokenOut(
        access_token=access_token,
        user=out(user),
    )


@router.post("/refresh", response_model=RefreshOut)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_session),
):
    """Rotate a refresh token and return a new access token."""
    if not refresh_token:
        raise AppError("UNAUTHORIZED", "Refresh token missing.", 401)

    token_hash = hash_token(refresh_token)
    row = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )

    if not row or row.expires_at <= datetime.now(timezone.utc):
        raise AppError(
            "UNAUTHORIZED",
            "Refresh token is invalid or expired.",
            401,
        )

    if row.revoked_at:
        # Reuse detection: revoke every active refresh token for this user.
        await session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == row.user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await session.commit()
        response.delete_cookie("refresh_token", path="/")
        raise AppError(
            "UNAUTHORIZED",
            "Refresh token reuse detected. Please sign in again.",
            401,
        )

    row.revoked_at = datetime.now(timezone.utc)
    user = await session.get(User, row.user_id)
    if not user:
        raise AppError("UNAUTHORIZED", "User not found.", 401)

    access_token = create_access_token(str(user.id), user.role.value)
    new_refresh_token = secrets.token_urlsafe(48)

    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(new_refresh_token),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    await session.commit()

    response.set_cookie(
        "refresh_token",
        new_refresh_token,
        **_refresh_cookie_options(),
    )

    return RefreshOut(access_token=access_token)


@router.post("/logout")
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_session),
):
    """Revoke the current refresh token and clear the browser cookie."""
    if refresh_token:
        row = await session.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_token(refresh_token)
            )
        )
        if row:
            row.revoked_at = datetime.now(timezone.utc)
            await session.commit()

    response.delete_cookie("refresh_token", path="/")
    return {"message": "Logged out."}


@router.get("/me", response_model=UserOut)
async def me(user=Depends(get_current_user)):
    """Return the currently authenticated user's public profile."""
    return out(user)


@router.post("/verify-email")
async def verify_email(
    data: VerifyOTPIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Verify a new account using its email OTP."""
    ip = request.client.host if request.client else "unknown"
    email = data.email.lower().strip()

    await check_rate_limit(session, f"verify-email:ip:{ip}", 5, 900)
    await check_rate_limit(session, f"verify-email:email:{email}", 5, 900)

    row = await session.scalar(
        select(OTPCode)
        .where(
            OTPCode.email == email,
            OTPCode.purpose == OTTPurpose.email_verify,
            OTPCode.consumed_at.is_(None),
        )
        .order_by(OTPCode.created_at.desc())
    )

    if not row:
        raise AppError(
            "OTP_INVALID",
            "Invalid or expired email verification code.",
            400,
        )
    if row.expires_at <= datetime.now(timezone.utc):
        raise AppError("OTP_EXPIRED", "OTP has expired.", 400)
    if row.attempts >= settings.OTP_MAX_ATTEMPTS:
        row.consumed_at = datetime.now(timezone.utc)
        await session.commit()
        raise AppError("OTP_ATTEMPTS_EXCEEDED", "Too many attempts.", 400)
    if not verify_password(data.otp, row.code_hash):
        row.attempts += 1
        await session.commit()
        raise AppError(
            "OTP_INVALID",
            "Invalid or expired email verification code.",
            400,
        )

    row.consumed_at = datetime.now(timezone.utc)
    user = await session.scalar(select(User).where(User.email == row.email))
    user.is_email_verified = True
    await session.commit()

    return {"message": "Email verified."}


@router.post("/forgot-password")
async def forgot(
    data: ForgotIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Start password recovery without revealing whether an email exists."""
    ip = request.client.host if request.client else "unknown"
    email = data.email.lower().strip()

    await check_rate_limit(session, f"forgot:ip:{ip}", 3, 900)
    await check_rate_limit(session, f"forgot:email:{email}", 3, 900)

    user = await session.scalar(select(User).where(User.email == email))
    if user:
        await create_otp(session, user.email, OTTPurpose.password_reset)

    return {"message": "If the email exists, a verification code has been sent."}


@router.post("/verify-otp")
async def verify(
    data: VerifyOTPIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Verify the password-reset OTP and issue a short-lived reset token."""
    ip = request.client.host if request.client else "unknown"
    email = data.email.lower().strip()

    await check_rate_limit(session, f"verify-otp:ip:{ip}", 5, 900)
    await check_rate_limit(session, f"verify-otp:email:{email}", 5, 900)

    row = await session.scalar(
        select(OTPCode)
        .where(
            OTPCode.email == email,
            OTPCode.purpose == OTTPurpose.password_reset,
            OTPCode.consumed_at.is_(None),
        )
        .order_by(OTPCode.created_at.desc())
    )

    if not row:
        raise AppError("OTP_INVALID", "Invalid OTP.", 400)
    if row.expires_at <= datetime.now(timezone.utc):
        raise AppError("OTP_EXPIRED", "OTP has expired.", 400)
    if row.attempts >= settings.OTP_MAX_ATTEMPTS:
        row.consumed_at = datetime.now(timezone.utc)
        await session.commit()
        raise AppError("OTP_ATTEMPTS_EXCEEDED", "Too many attempts.", 400)
    if not verify_password(data.otp, row.code_hash):
        row.attempts += 1
        await session.commit()
        raise AppError("OTP_INVALID", "Invalid OTP.", 400)

    row.consumed_at = datetime.now(timezone.utc)
    await session.commit()

    reset_token = create_access_token(
        str(row.id),
        "reset",
        minutes=15,
        purpose="password_reset",
    )
    return {"reset_token": reset_token, "message": "OTP verified."}


@router.post("/resend-otp")
async def resend(
    data: ForgotIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Resend a password-reset OTP after the configured cooldown."""
    email = data.email.lower().strip()
    await check_rate_limit(
        session,
        f"resend:email:{email}",
        1,
        settings.OTP_RESEND_COOLDOWN_SECONDS,
    )
    return await forgot(data, request, session)


@router.post("/resend-verification")
async def resend_verification(
    data: ForgotIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Resend the account-verification OTP for an unverified account."""
    ip = request.client.host if request.client else "unknown"
    email = data.email.lower().strip()

    await check_rate_limit(session, f"resend-verification:ip:{ip}", 3, 900)
    await check_rate_limit(
        session,
        f"resend-verification:email:{email}",
        1,
        settings.OTP_RESEND_COOLDOWN_SECONDS,
    )

    user = await session.scalar(select(User).where(User.email == email))
    if user and not user.is_email_verified:
        await create_otp(session, email, OTTPurpose.email_verify)

    return {
        "message": "If the account exists and is unverified, a new verification code has been sent."
    }


@router.post("/reset-password")
async def reset(
    data: ResetIn,
    session: AsyncSession = Depends(get_session),
):
    """Set a new password using a verified, short-lived reset token."""
    try:
        payload = decode_token(data.reset_token)
    except Exception as exc:
        raise AppError("UNAUTHORIZED", "Invalid reset token.", 401) from exc

    if payload.get("purpose") != "password_reset":
        raise AppError("UNAUTHORIZED", "Invalid reset token.", 401)

    otp = await session.get(OTPCode, payload["sub"])
    if not otp or not otp.consumed_at or otp.reset_token_used_at is not None:
        raise AppError(
            "UNAUTHORIZED",
            "Reset token is not valid or has already been used.",
            401,
        )

    if otp.created_at < datetime.now(timezone.utc) - timedelta(minutes=15):
        raise AppError("UNAUTHORIZED", "Reset token has expired.", 401)

    user = await session.scalar(select(User).where(User.email == otp.email))
    if not user or not user.is_active:
        raise AppError("UNAUTHORIZED", "Account is not available.", 401)

    validate_password_strength(data.new_password)

    otp.reset_token_used_at = datetime.now(timezone.utc)
    user.password_hash = hash_password(data.new_password)

    # A password change invalidates all active refresh tokens for the account.
    await session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
    )
    await session.commit()

    return {"message": "Password reset successfully."}


@router.patch("/me", response_model=UserOut)
async def patch(
    data: ProfilePatch,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update the authenticated user's editable profile fields."""
    if data.full_name is not None:
        user.full_name = data.full_name.strip()
    if data.phone is not None:
        user.phone = data.phone

    await session.commit()
    return out(user)


@router.post("/change-password")
async def change(
    data: ChangePasswordIn,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Change the authenticated user's password."""
    validate_password_strength(data.new_password)

    if not verify_password(data.current_password, user.password_hash):
        raise AppError("UNAUTHORIZED", "Current password is incorrect.", 400)

    user.password_hash = hash_password(data.new_password)
    user.must_change_password = False
    await session.commit()

    return {"message": "Password changed."}
