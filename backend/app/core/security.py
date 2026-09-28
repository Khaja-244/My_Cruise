"""Security helpers for passwords, JWTs, and one-time passwords."""

from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import string

import bcrypt
import jwt

from app.core.config import settings


def validate_password_strength(password: str) -> None:
    """Validate the minimum password requirements used by the application."""
    has_letter = any(character.isalpha() for character in password)
    has_digit = any(character.isdigit() for character in password)

    if len(password) < 8 or not has_letter or not has_digit:
        from app.core.exceptions import AppError

        raise AppError(
            "VALIDATION_ERROR",
            "Password must be at least 8 characters and contain a letter and a number.",
            422,
        )


def hash_password(password: str) -> str:
    """Create a bcrypt password hash."""
    return bcrypt.hashpw(
        password.encode(),
        bcrypt.gensalt(rounds=12),
    ).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """Check a plain-text password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except (ValueError, TypeError):
        return False


def hash_token(value: str) -> str:
    """Create a SHA-256 hash for refresh-token storage and lookup."""
    return hashlib.sha256(value.encode()).hexdigest()


def create_access_token(
    user_id: str,
    role: str,
    jti: str | None = None,
    minutes: int | None = None,
    purpose: str | None = None,
):
    """Create a signed JWT access or short-lived purpose-specific token."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "jti": jti or secrets.token_hex(12),
        "iat": now,
        "exp": now
        + timedelta(minutes=minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }

    if purpose:
        payload["purpose"] = purpose

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str):
    """Decode and validate a JWT using the configured signing key."""
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )


def generate_otp(length: int | None = None) -> str:
    """Generate a numeric OTP using a cryptographically secure random source."""
    otp_length = length or settings.OTP_LENGTH
    return "".join(secrets.choice(string.digits) for _ in range(otp_length))
