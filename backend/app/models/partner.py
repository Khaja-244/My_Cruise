"""Database models for partner agencies and partner websites."""

from datetime import datetime, timezone
import enum
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PartnerStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    disabled = "disabled"
    rejected = "rejected"


class PartnerApplicationStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class IntegrationStatus(str, enum.Enum):
    connected = "connected"
    suspended = "suspended"


def idcol():
    """Create the standard UUID primary-key column used by partner tables."""
    return mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


def utc_now():
    """Return a timezone-aware UTC timestamp for audit fields."""
    return datetime.now(timezone.utc)


class Partner(Base):
    __tablename__ = "partners"

    id: Mapped[uuid.UUID] = idcol()
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        unique=True,
    )
    business_name: Mapped[str] = mapped_column(String(200))
    contact_name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[PartnerStatus] = mapped_column(
        SAEnum(
            PartnerStatus,
            name="partner_status",
            create_type=False,
        ),
        default=PartnerStatus.active,
    )
    integration_status: Mapped[IntegrationStatus] = mapped_column(
        SAEnum(
            IntegrationStatus,
            name="integration_status",
            create_type=False,
        ),
        default=IntegrationStatus.suspended,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class PartnerApplication(Base):
    __tablename__ = "partner_applications"

    id: Mapped[uuid.UUID] = idcol()
    applicant_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    business_name: Mapped[str] = mapped_column(String(200))
    contact_name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(40))
    documents: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[PartnerApplicationStatus] = mapped_column(
        SAEnum(
            PartnerApplicationStatus,
            name="partner_application_status",
            create_type=False,
        ),
        default=PartnerApplicationStatus.pending,
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    review_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PartnerApiKey(Base):
    __tablename__ = "partner_api_keys"

    id: Mapped[uuid.UUID] = idcol()
    partner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("partners.id", ondelete="CASCADE")
    )
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    key_prefix: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=60)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PartnerWebsite(Base):
    __tablename__ = "partner_websites"

    id: Mapped[uuid.UUID] = idcol()
    partner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("partners.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(160))
    website_url: Mapped[str] = mapped_column(Text)
    integration_status: Mapped[IntegrationStatus] = mapped_column(
        SAEnum(
            IntegrationStatus,
            name="integration_status",
            create_type=False,
        )
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )
    last_connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PartnerCruiseExposure(Base):
    __tablename__ = "partner_cruise_exposures"

    id: Mapped[uuid.UUID] = idcol()
    partner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("partners.id", ondelete="CASCADE")
    )
    partner_website_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("partner_websites.id", ondelete="CASCADE"),
        nullable=True,
    )
    cruise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cruises.id", ondelete="CASCADE")
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint(
            "partner_website_id",
            "cruise_id",
            name="uq_partner_website_cruise_exposure",
        ),
        Index(
            "uq_partner_cruise_legacy_exposure",
            "partner_id",
            "cruise_id",
            unique=True,
            postgresql_where=text("partner_website_id IS NULL"),
        ),
    )


class PartnerApiUsage(Base):
    __tablename__ = "partner_api_usage"

    id: Mapped[uuid.UUID] = idcol()
    api_key_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("partner_api_keys.id", ondelete="CASCADE")
    )
    method: Mapped[str] = mapped_column(String(10))
    path: Mapped[str] = mapped_column(Text)
    status_code: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )
