from datetime import datetime, date, time, timezone
import enum
import uuid
from sqlalchemy import String, Text, Boolean, Integer, BigInteger, DateTime, Date, Time, ForeignKey, UniqueConstraint, Enum as SAEnum, Numeric, CHAR
from sqlalchemy.dialects.postgresql import UUID, JSONB, CITEXT
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class StrEnum(str, enum.Enum):
    """String-backed enum used by PostgreSQL enum columns."""

class UserRole(StrEnum):
    traveler = 'traveler'
    admin = 'admin'
    partner = 'partner'

class OTTPurpose(StrEnum):
    password_reset = 'password_reset'
    email_verify = 'email_verify'

class CruiseStatus(StrEnum):
    draft = 'draft'
    published = 'published'
    archived = 'archived'

class ApprovalStatus(StrEnum):
    approved = 'approved'
    pending = 'pending'
    rejected = 'rejected'

class SailingStatus(StrEnum):
    scheduled = 'scheduled'
    open = 'open'
    closed = 'closed'
    departed = 'departed'
    cancelled = 'cancelled'

class InventoryStatus(StrEnum):
    available = 'available'
    held = 'held'
    booked = 'booked'
    blocked = 'blocked'

class BookingChannel(StrEnum):
    direct = 'direct'
    partner = 'partner'

class CommissionType(StrEnum):
    percent = 'percent'
    flat = 'flat'

class BookingStatus(StrEnum):
    pending_payment = 'pending_payment'
    confirmed = 'confirmed'
    cancellation_requested = 'cancellation_requested'
    cancelled = 'cancelled'
    refunded = 'refunded'
    partially_refunded = 'partially_refunded'
    expired = 'expired'
    payment_failed = 'payment_failed'

class PaymentStatus(StrEnum):
    requires_payment = 'requires_payment'
    processing = 'processing'
    succeeded = 'succeeded'
    failed = 'failed'
    cancelled = 'cancelled'

class CancellationStatus(StrEnum):
    pending = 'pending'
    approved = 'approved'
    rejected = 'rejected'

class RefundStatus(StrEnum):
    pending = 'pending'
    processing = 'processing'
    succeeded = 'succeeded'
    failed = 'failed'

class NotificationType(StrEnum):
    booking_confirmed = 'booking_confirmed'
    booking_cancelled = 'booking_cancelled'
    cancellation_requested = 'cancellation_requested'
    refund_approved = 'refund_approved'
    refund_rejected = 'refund_rejected'
    refund_completed = 'refund_completed'
    refund_failed = 'refund_failed'
    new_cruise = 'new_cruise'
    payment_failed = 'payment_failed'

def idcol():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

class User(Base):
    __tablename__ = 'users'
    id: Mapped[uuid.UUID] = idcol()
    full_name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(CITEXT, unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(40))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole, name='user_role', create_type=False), default=UserRole.traveler)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class RefreshToken(Base):
    __tablename__ = 'refresh_tokens'
    id: Mapped[uuid.UUID] = idcol()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    token_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(String(64))

class OTPCode(Base):
    __tablename__ = 'otp_codes'
    id: Mapped[uuid.UUID] = idcol()
    email: Mapped[str] = mapped_column(String(255), index=True)
    purpose: Mapped[OTTPurpose] = mapped_column(SAEnum(OTTPurpose, name='otp_purpose', create_type=False))
    code_hash: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    reset_token_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class DeviceToken(Base):
    __tablename__ = 'device_tokens'
    id: Mapped[uuid.UUID] = idcol()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    fcm_token: Mapped[str] = mapped_column(String(512), unique=True)
    platform: Mapped[str] = mapped_column(String(30))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class Ship(Base):
    __tablename__ = 'ships'
    id: Mapped[uuid.UUID] = idcol()
    owner_type: Mapped[str] = mapped_column(String(20), default='platform')
    partner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('partners.id', ondelete='SET NULL'))
    name: Mapped[str] = mapped_column(String(160))
    operator_name: Mapped[str] = mapped_column(String(160))
    deck_count: Mapped[int] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class Port(Base):
    __tablename__ = 'ports'
    id: Mapped[uuid.UUID] = idcol()
    name: Mapped[str] = mapped_column(String(160))
    city: Mapped[str] = mapped_column(String(120))
    country: Mapped[str] = mapped_column(String(120))
    code: Mapped[str] = mapped_column(String(10), unique=True)
    timezone: Mapped[str] = mapped_column(String(80))

class RefundPolicy(Base):
    __tablename__ = 'refund_policies'
    id: Mapped[uuid.UUID] = idcol()
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class Cruise(Base):
    __tablename__ = 'cruises'
    id: Mapped[uuid.UUID] = idcol()
    partner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('partners.id', ondelete='SET NULL'))
    ship_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('ships.id'))
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(220), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    sailing_days: Mapped[int] = mapped_column(Integer)
    embark_port_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('ports.id'))
    disembark_port_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('ports.id'))
    status: Mapped[CruiseStatus] = mapped_column(SAEnum(CruiseStatus, name='cruise_status', create_type=False), default=CruiseStatus.draft)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    base_price_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    currency: Mapped[str] = mapped_column(CHAR(3), default='USD')
    approval_status: Mapped[ApprovalStatus] = mapped_column(SAEnum(ApprovalStatus, name='approval_status', create_type=False), default=ApprovalStatus.approved)
    owner_type: Mapped[str] = mapped_column(String(20), default='platform')
    commission_type: Mapped[CommissionType | None] = mapped_column(SAEnum(CommissionType, name='commission_type', create_type=False), nullable=True)
    commission_value: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    refund_policy_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('refund_policies.id', ondelete='SET NULL'))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class CruiseImage(Base):
    __tablename__ = 'cruise_images'
    id: Mapped[uuid.UUID] = idcol()
    cruise_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('cruises.id', ondelete='CASCADE'))
    url: Mapped[str] = mapped_column(Text)
    alt_text: Mapped[str | None] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_cover: Mapped[bool] = mapped_column(Boolean, default=False)

class CruiseItinerary(Base):
    __tablename__ = 'cruise_itineraries'
    id: Mapped[uuid.UUID] = idcol()
    cruise_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('cruises.id', ondelete='CASCADE'))
    day_number: Mapped[int] = mapped_column(Integer)
    port_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('ports.id', ondelete='SET NULL'))
    arrival_time: Mapped[time | None] = mapped_column(Time)
    departure_time: Mapped[time | None] = mapped_column(Time)
    description: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (UniqueConstraint('cruise_id', 'day_number'),)

class Sailing(Base):
    __tablename__ = 'sailings'
    id: Mapped[uuid.UUID] = idcol()
    cruise_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('cruises.id', ondelete='CASCADE'))
    departure_date: Mapped[date] = mapped_column(Date)
    return_date: Mapped[date] = mapped_column(Date)
    status: Mapped[SailingStatus] = mapped_column(SAEnum(SailingStatus, name='sailing_status', create_type=False), default=SailingStatus.scheduled)
    booking_closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    port_fee_per_guest_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    __table_args__ = (UniqueConstraint('cruise_id', 'departure_date'),)

class Deck(Base):
    __tablename__ = 'decks'
    id: Mapped[uuid.UUID] = idcol()
    ship_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('ships.id', ondelete='CASCADE'))
    deck_number: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(100))
    __table_args__ = (UniqueConstraint('ship_id', 'deck_number'),)

class CabinType(Base):
    """Defines an accommodation category and its passenger capacity/pricing."""

    __tablename__ = 'cabin_types'
    id: Mapped[uuid.UUID] = idcol()
    cruise_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('cruises.id', ondelete='CASCADE'))
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text)
    max_occupancy: Mapped[int] = mapped_column(Integer)
    base_price_cents: Mapped[int] = mapped_column(BigInteger)
    price_per_extra_guest_cents: Mapped[int] = mapped_column(BigInteger, default=0)

class Amenity(Base):
    __tablename__ = 'amenities'
    id: Mapped[uuid.UUID] = idcol()
    name: Mapped[str] = mapped_column(String(120), unique=True)
    icon_key: Mapped[str | None] = mapped_column(String(80))
    category: Mapped[str | None] = mapped_column(String(80))

class CabinTypeAmenity(Base):
    __tablename__ = 'cabin_type_amenities'
    cabin_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('cabin_types.id', ondelete='CASCADE'), primary_key=True)
    amenity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('amenities.id', ondelete='CASCADE'), primary_key=True)

class Cabin(Base):
    """Represents one physical passenger room/accommodation on a ship."""

    __tablename__ = 'cabins'
    id: Mapped[uuid.UUID] = idcol()
    ship_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('ships.id', ondelete='CASCADE'))
    deck_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('decks.id', ondelete='CASCADE'))
    cabin_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('cabin_types.id'))
    cabin_number: Mapped[str] = mapped_column(String(40))
    max_occupancy: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint('ship_id', 'cabin_number'),)

class Booking(Base):
    """Represents a traveler or partner booking for one sailing."""

    __tablename__ = 'bookings'
    id: Mapped[uuid.UUID] = idcol()
    booking_reference: Mapped[str] = mapped_column(String(12), unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))
    sailing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('sailings.id'))
    partner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('partners.id', ondelete='SET NULL'))
    channel: Mapped[BookingChannel] = mapped_column(SAEnum(BookingChannel, name='booking_channel', create_type=False), default=BookingChannel.direct)
    status: Mapped[BookingStatus] = mapped_column(SAEnum(BookingStatus, name='booking_status', create_type=False))
    guest_count: Mapped[int] = mapped_column(Integer)
    subtotal_cents: Mapped[int] = mapped_column(BigInteger)
    tax_cents: Mapped[int] = mapped_column(BigInteger)
    total_cents: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(CHAR(3), default='USD')
    customer_name: Mapped[str | None] = mapped_column(String(160))
    customer_email: Mapped[str | None] = mapped_column(String(255))
    customer_phone: Mapped[str | None] = mapped_column(String(40))
    commission_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    hold_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class CabinInventory(Base):
    """Tracks the shared availability of one cabin for one sailing."""

    __tablename__ = 'cabin_inventory'
    id: Mapped[uuid.UUID] = idcol()
    sailing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('sailings.id', ondelete='CASCADE'))
    cabin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('cabins.id', ondelete='CASCADE'))
    status: Mapped[InventoryStatus] = mapped_column(SAEnum(InventoryStatus, name='inventory_status', create_type=False), default=InventoryStatus.available)
    held_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id'))
    hold_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    booking_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('bookings.id', ondelete='SET NULL'))
    price_cents: Mapped[int] = mapped_column(BigInteger)
    version: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    __table_args__ = (UniqueConstraint('sailing_id', 'cabin_id', name='uq_sailing_cabin'),)

class BookingCabin(Base):
    """Stores the cabins and occupancy selected for a booking."""

    __tablename__ = 'booking_cabins'
    id: Mapped[uuid.UUID] = idcol()
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('bookings.id', ondelete='CASCADE'))
    cabin_inventory_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('cabin_inventory.id'))
    cabin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('cabins.id'))
    occupancy: Mapped[int] = mapped_column(Integer)
    price_cents: Mapped[int] = mapped_column(BigInteger)
    __table_args__ = (UniqueConstraint('booking_id', 'cabin_id'),)

class BookingGuest(Base):
    __tablename__ = 'booking_guests'
    id: Mapped[uuid.UUID] = idcol()
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('bookings.id', ondelete='CASCADE'))
    cabin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('cabins.id'))
    full_name: Mapped[str] = mapped_column(String(160))
    date_of_birth: Mapped[date] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(40))
    nationality: Mapped[str | None] = mapped_column(String(100))
    passport_number: Mapped[str | None] = mapped_column(String(100))
    is_lead_guest: Mapped[bool] = mapped_column(Boolean, default=False)

class Payment(Base):
    __tablename__ = 'payments'
    id: Mapped[uuid.UUID] = idcol()
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('bookings.id', ondelete='CASCADE'))
    stripe_payment_intent_id: Mapped[str] = mapped_column(String(255), unique=True)
    stripe_charge_id: Mapped[str | None] = mapped_column(String(255))
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(CHAR(3))
    status: Mapped[PaymentStatus] = mapped_column(SAEnum(PaymentStatus, name='payment_status', create_type=False))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class WebhookEvent(Base):
    __tablename__ = 'webhook_events'
    id: Mapped[uuid.UUID] = idcol()
    stripe_event_id: Mapped[str] = mapped_column(String(255), unique=True)
    event_type: Mapped[str] = mapped_column(String(160))
    payload: Mapped[dict] = mapped_column(JSONB)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class RefundPolicyRule(Base):
    __tablename__ = 'refund_policy_rules'
    id: Mapped[uuid.UUID] = idcol()
    policy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('refund_policies.id', ondelete='CASCADE'))
    min_days_before_departure: Mapped[int] = mapped_column(Integer)
    max_days_before_departure: Mapped[int | None] = mapped_column(Integer)
    refund_percent: Mapped[float] = mapped_column(Numeric(5, 2))
    flat_fee_cents: Mapped[int] = mapped_column(BigInteger, default=0)

class CancellationRequest(Base):
    __tablename__ = 'cancellation_requests'
    id: Mapped[uuid.UUID] = idcol()
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('bookings.id', ondelete='CASCADE'))
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[CancellationStatus] = mapped_column(SAEnum(CancellationStatus, name='cancellation_status', create_type=False), default=CancellationStatus.pending)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id'))
    admin_note: Mapped[str | None] = mapped_column(Text)
    policy_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    calculated_refund_cents: Mapped[int | None] = mapped_column(BigInteger)
    final_refund_cents: Mapped[int | None] = mapped_column(BigInteger)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class Refund(Base):
    __tablename__ = 'refunds'
    id: Mapped[uuid.UUID] = idcol()
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('bookings.id'))
    cancellation_request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('cancellation_requests.id'))
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('payments.id'))
    stripe_refund_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[RefundStatus] = mapped_column(SAEnum(RefundStatus, name='refund_status', create_type=False), default=RefundStatus.pending)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class SavedCruise(Base):
    __tablename__ = 'saved_cruises'
    id: Mapped[uuid.UUID] = idcol()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    cruise_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('cruises.id', ondelete='CASCADE'))
    sailing_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('sailings.id', ondelete='CASCADE'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    __table_args__ = (UniqueConstraint('user_id', 'cruise_id', 'sailing_id'),)

class Notification(Base):
    __tablename__ = 'notifications'
    id: Mapped[uuid.UUID] = idcol()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    type: Mapped[NotificationType] = mapped_column(SAEnum(NotificationType, name='notification_type', create_type=False))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    data: Mapped[dict | None] = mapped_column(JSONB)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_push: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_email: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id: Mapped[uuid.UUID] = idcol()
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    action: Mapped[str] = mapped_column(String(120))
    entity_type: Mapped[str] = mapped_column(String(120))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class RateLimitCounter(Base):
    __tablename__ = 'rate_limit_counters'
    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    count: Mapped[int] = mapped_column(Integer, default=0)
from app.models.partner import Partner, PartnerApplication, PartnerApiKey, PartnerWebsite, PartnerCruiseExposure, PartnerApiUsage, PartnerStatus, PartnerApplicationStatus, IntegrationStatus
