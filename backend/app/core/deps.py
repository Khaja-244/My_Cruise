"""FastAPI dependencies shared by authenticated API routes."""

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.exceptions import AppError
from app.core.security import decode_token
from app.models import User


# HTTPBearer reads the Authorization: Bearer <token> header for us.
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
):
    """Return the active user represented by the access token."""
    if not credentials:
        raise AppError("UNAUTHORIZED", "Authentication required.", 401)

    try:
        payload = decode_token(credentials.credentials)

        # Password-reset/verification tokens must never be accepted as access tokens.
        if payload.get("purpose"):
            raise AppError("UNAUTHORIZED", "Invalid access token.", 401)

        user = await session.scalar(select(User).where(User.id == payload["sub"]))
    except AppError:
        raise
    except Exception:
        # Do not leak token parsing details to the client.
        user = None

    if not user or not user.is_active:
        raise AppError("UNAUTHORIZED", "Invalid or expired access token.", 401)

    if user.must_change_password and request.url.path not in {
        f"{settings.API_PREFIX}/auth/change-password",
        f"{settings.API_PREFIX}/auth/me",
    }:
        raise AppError(
            "FORBIDDEN",
            "Password change is required before continuing.",
            403,
        )

    return user


async def require_admin(user: User = Depends(get_current_user)):
    """Allow only users with the admin role."""
    if user.role.value != "admin":
        raise AppError("FORBIDDEN", "Admin access required.", 403)
    return user


def pagination(page: int = 1, page_size: int = 20) -> tuple[int, int]:
    """Normalize common page parameters to safe limits."""
    return max(page, 1), min(max(page_size, 1), 100)


def idempotency_key(
    value: str | None = Header(default=None, alias="Idempotency-Key"),
) -> str:
    """Validate the retry key required by booking endpoints."""
    if not value:
        raise AppError(
            "DUPLICATE_REQUEST",
            "Idempotency-Key header is required.",
            400,
        )

    value = value.strip()
    if not value or len(value) > 255:
        raise AppError(
            "VALIDATION_ERROR",
            "Idempotency-Key must be between 1 and 255 characters.",
            422,
        )

    return value
