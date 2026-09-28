"""Authentication and rate limiting for partner website API keys."""

import hashlib
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions import AppError
from app.models import (
    IntegrationStatus,
    Partner,
    PartnerApiKey,
    PartnerApiUsage,
    PartnerStatus,
    PartnerWebsite,
)


def generate_partner_api_key():
    """Create a raw key plus its safe database representation.

    Only the hash is stored in the database. The raw value is shown once when
    an administrator creates a key and should be treated like a password.
    """
    raw_key = f"mc_live_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:16]
    return raw_key, key_hash, key_prefix


async def require_partner_api_key(
    request: Request,
    x_api_key: str | None = Header(
        default=None,
        alias="X-Partner-API-Key",
    ),
    x_website_id: str | None = Header(
        default=None,
        alias="X-Partner-Website-ID",
    ),
    session: AsyncSession = Depends(get_session),
):
    """Authenticate a partner API request and optionally scope it to a website."""
    if not x_api_key:
        raise AppError(
            "UNAUTHORIZED",
            "X-Partner-API-Key header is required.",
            401,
        )

    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    api_key = await session.scalar(
        select(PartnerApiKey).where(
            PartnerApiKey.key_hash == key_hash,
            PartnerApiKey.active.is_(True),
        )
    )
    if not api_key:
        raise AppError("UNAUTHORIZED", "Invalid or revoked partner API key.", 401)

    partner = await session.get(Partner, api_key.partner_id)
    if (
        not partner
        or partner.status != PartnerStatus.active
        or partner.integration_status != IntegrationStatus.connected
    ):
        raise AppError("FORBIDDEN", "Partner integration is inactive.", 403)

    # Simple one-minute request counter for the API key.
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=1)
    request_count = await session.scalar(
        select(func.count())
        .select_from(PartnerApiUsage)
        .where(
            PartnerApiUsage.api_key_id == api_key.id,
            PartnerApiUsage.created_at >= cutoff,
        )
    )
    if request_count >= api_key.rate_limit_per_minute:
        raise AppError("RATE_LIMITED", "Partner API rate limit exceeded.", 429)

    usage = PartnerApiUsage(
        api_key_id=api_key.id,
        method=request.method,
        path=request.url.path,
        status_code=0,
    )
    session.add(usage)
    await session.flush()
    await session.commit()

    request.state.partner_api_key_id = api_key.id
    request.state.partner_website_id = None

    if x_website_id:
        try:
            website_id = uuid.UUID(x_website_id)
        except ValueError as exc:
            raise AppError(
                "VALIDATION_ERROR",
                "Invalid X-Partner-Website-ID.",
                422,
            ) from exc

        website = await session.scalar(
            select(PartnerWebsite).where(
                PartnerWebsite.id == website_id,
                PartnerWebsite.partner_id == partner.id,
                PartnerWebsite.integration_status == IntegrationStatus.connected,
            )
        )
        if not website:
            raise AppError(
                "FORBIDDEN",
                "Partner website is not connected or does not belong to this partner.",
                403,
            )

        request.state.partner_website_id = website.id

    request.state.partner_api_usage_id = usage.id
    request.state.partner_api_started = time.monotonic()
    return partner
