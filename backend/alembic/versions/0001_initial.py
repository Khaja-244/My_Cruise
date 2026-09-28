"""Initial my_cruise Phase 1 schema.

The schema intentionally includes Phase 2 partner columns as nullable fields so
partner functionality can be added without rewriting booking/inventory tables.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, CITEXT, ENUM
import uuid


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # PostgreSQL extensions used by the production schema.
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    # Create PostgreSQL ENUM types once.
    #
    # These types are created manually with CREATE TYPE below.
    # The enum() helper later references these existing types with
    # create_type=False so SQLAlchemy does not try to create them again.
    enum_values = {
        "user_role": "'traveler','admin'",
        "otp_purpose": "'password_reset','email_verify'",
        "cruise_status": "'draft','published','archived'",
        "approval_status": "'approved','pending','rejected'",
        "sailing_status": "'scheduled','open','closed','departed','cancelled'",
        "inventory_status": "'available','held','booked','blocked'",
        "booking_channel": "'direct','partner'",
        "booking_status": (
            "'pending_payment','confirmed','cancellation_requested',"
            "'cancelled','refunded','partially_refunded','expired','payment_failed'"
        ),
        "payment_status": (
            "'requires_payment','processing','succeeded','failed','cancelled'"
        ),
        "cancellation_status": "'pending','approved','rejected'",
        "refund_status": "'pending','processing','succeeded','failed'",
        "notification_type": (
            "'booking_confirmed','booking_cancelled','cancellation_requested',"
            "'refund_approved','refund_rejected','refund_completed',"
            "'new_cruise','payment_failed'"
        ),
    }

    for name, values in enum_values.items():
        op.execute(f"CREATE TYPE {name} AS ENUM ({values})")

    def enum(name):
        """
        Reference an already-created PostgreSQL ENUM type.

        The ENUM types are created explicitly above, so SQLAlchemy must not
        attempt to create them again when creating the table columns.
        """
        return ENUM(name=name, create_type=False)

    def uid():
        """Create a standard UUID primary-key column."""
        return sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
        )

    # -------------------------------------------------------------------------
    # USERS / AUTHENTICATION
    # -------------------------------------------------------------------------

    op.create_table(
        "users",
        uid(),
        sa.Column("full_name", sa.String(160), nullable=False),
        sa.Column("email", CITEXT, nullable=False, unique=True),
        sa.Column("phone", sa.String(40)),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "role",
            enum("user_role"),
            nullable=False,
            server_default="traveler",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.Column(
            "is_email_verified",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "refresh_tokens",
        uid(),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("user_agent", sa.Text()),
        sa.Column("ip", sa.String(64)),
    )

    op.create_index(
        "ix_refresh_user",
        "refresh_tokens",
        ["user_id", "revoked_at"],
    )

    op.create_table(
        "otp_codes",
        uid(),
        sa.Column("email", CITEXT, nullable=False),
        sa.Column("purpose", enum("otp_purpose"), nullable=False),
        sa.Column("code_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "attempts",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("reset_token_used_at", sa.DateTime(timezone=True)),
    )

    op.create_index(
        "ix_otp_lookup",
        "otp_codes",
        ["email", "purpose", "consumed_at"],
    )

    op.create_table(
        "device_tokens",
        uid(),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "fcm_token",
            sa.String(512),
            unique=True,
            nullable=False,
        ),
        sa.Column("platform", sa.String(30), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
    )

    # -------------------------------------------------------------------------
    # CRUISE CATALOG
    # -------------------------------------------------------------------------

    op.create_table(
        "ships",
        uid(),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("operator_name", sa.String(160), nullable=False),
        sa.Column("deck_count", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "ports",
        uid(),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("city", sa.String(120), nullable=False),
        sa.Column("country", sa.String(120), nullable=False),
        sa.Column("code", sa.String(10), unique=True, nullable=False),
        sa.Column("timezone", sa.String(80), nullable=False),
    )

    op.execute(
        "CREATE INDEX ix_ports_search ON ports "
        "USING GIN (to_tsvector('english', "
        "coalesce(name,'') || ' ' || coalesce(city,'')))"
    )

    op.create_table(
        "cruises",
        uid(),
        sa.Column("partner_id", UUID(as_uuid=True)),
        sa.Column(
            "ship_id",
            UUID(as_uuid=True),
            sa.ForeignKey("ships.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(220), unique=True, nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("sailing_days", sa.Integer(), nullable=False),
        sa.Column(
            "embark_port_id",
            UUID(as_uuid=True),
            sa.ForeignKey("ports.id"),
            nullable=False,
        ),
        sa.Column(
            "disembark_port_id",
            UUID(as_uuid=True),
            sa.ForeignKey("ports.id"),
            nullable=False,
        ),
        sa.Column(
            "status",
            enum("cruise_status"),
            server_default="draft",
            nullable=False,
        ),
        sa.Column(
            "is_featured",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column(
            "base_price_cents",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "currency",
            sa.CHAR(3),
            server_default="USD",
            nullable=False,
        ),
        sa.Column(
            "approval_status",
            enum("approval_status"),
            server_default="approved",
            nullable=False,
        ),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_cruise_status_approval",
        "cruises",
        ["status", "approval_status"],
    )

    op.create_index(
        "ix_cruises_slug",
        "cruises",
        ["slug"],
    )

    op.execute(
        "CREATE INDEX ix_cruises_search ON cruises "
        "USING GIN (to_tsvector('english', "
        "coalesce(name,'') || ' ' || coalesce(description,'')))"
    )

    op.create_table(
        "cruise_images",
        uid(),
        sa.Column(
            "cruise_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cruises.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("alt_text", sa.String(255)),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
        sa.Column(
            "is_cover",
            sa.Boolean(),
            server_default="false",
        ),
    )

    op.create_table(
        "cruise_itineraries",
        uid(),
        sa.Column(
            "cruise_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cruises.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("day_number", sa.Integer(), nullable=False),
        sa.Column(
            "port_id",
            UUID(as_uuid=True),
            sa.ForeignKey("ports.id", ondelete="SET NULL"),
        ),
        sa.Column("arrival_time", sa.Time()),
        sa.Column("departure_time", sa.Time()),
        sa.Column("description", sa.Text()),
        sa.UniqueConstraint("cruise_id", "day_number"),
    )

    op.create_table(
        "sailings",
        uid(),
        sa.Column(
            "cruise_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cruises.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("departure_date", sa.Date(), nullable=False),
        sa.Column("return_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            enum("sailing_status"),
            server_default="scheduled",
            nullable=False,
        ),
        sa.Column(
            "booking_closes_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "port_fee_per_guest_cents",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("cruise_id", "departure_date"),
    )

    op.create_index(
        "ix_sailings_status_date",
        "sailings",
        ["status", "departure_date"],
    )

    # -------------------------------------------------------------------------
    # SHIP / CABIN MANAGEMENT
    # -------------------------------------------------------------------------

    op.create_table(
        "decks",
        uid(),
        sa.Column(
            "ship_id",
            UUID(as_uuid=True),
            sa.ForeignKey("ships.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("deck_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.UniqueConstraint("ship_id", "deck_number"),
    )

    op.create_table(
        "cabin_types",
        uid(),
        sa.Column(
            "cruise_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cruises.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("max_occupancy", sa.Integer(), nullable=False),
        sa.Column("base_price_cents", sa.BigInteger(), nullable=False),
        sa.Column(
            "price_per_extra_guest_cents",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
    )

    op.create_table(
        "amenities",
        uid(),
        sa.Column("name", sa.String(120), unique=True, nullable=False),
        sa.Column("icon_key", sa.String(80)),
        sa.Column("category", sa.String(80)),
    )

    op.create_table(
        "cabin_type_amenities",
        sa.Column(
            "cabin_type_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cabin_types.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "amenity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("amenities.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_table(
        "cabins",
        uid(),
        sa.Column(
            "ship_id",
            UUID(as_uuid=True),
            sa.ForeignKey("ships.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "deck_id",
            UUID(as_uuid=True),
            sa.ForeignKey("decks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "cabin_type_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cabin_types.id"),
            nullable=False,
        ),
        sa.Column("cabin_number", sa.String(40), nullable=False),
        sa.Column("max_occupancy", sa.Integer(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.UniqueConstraint("ship_id", "cabin_number"),
    )

    # -------------------------------------------------------------------------
    # BOOKINGS / INVENTORY
    # -------------------------------------------------------------------------

    op.create_table(
        "bookings",
        uid(),
        sa.Column(
            "booking_reference",
            sa.String(12),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "sailing_id",
            UUID(as_uuid=True),
            sa.ForeignKey("sailings.id"),
            nullable=False,
        ),
        sa.Column("partner_id", UUID(as_uuid=True)),
        sa.Column(
            "channel",
            enum("booking_channel"),
            server_default="direct",
            nullable=False,
        ),
        sa.Column(
            "status",
            enum("booking_status"),
            nullable=False,
        ),
        sa.Column("guest_count", sa.Integer(), nullable=False),
        sa.Column("subtotal_cents", sa.BigInteger(), nullable=False),
        sa.Column("tax_cents", sa.BigInteger(), nullable=False),
        sa.Column("total_cents", sa.BigInteger(), nullable=False),
        sa.Column(
            "currency",
            sa.CHAR(3),
            server_default="USD",
            nullable=False,
        ),
        sa.Column(
            "commission_cents",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("hold_expires_at", sa.DateTime(timezone=True)),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column(
            "idempotency_key",
            sa.String(255),
            unique=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_bookings_user",
        "bookings",
        ["user_id", "created_at"],
    )

    op.create_index(
        "ix_bookings_sailing",
        "bookings",
        ["sailing_id", "status"],
    )

    op.create_table(
        "cabin_inventory",
        uid(),
        sa.Column(
            "sailing_id",
            UUID(as_uuid=True),
            sa.ForeignKey("sailings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "cabin_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cabins.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            enum("inventory_status"),
            server_default="available",
            nullable=False,
        ),
        sa.Column(
            "held_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
        ),
        sa.Column("hold_expires_at", sa.DateTime(timezone=True)),
        sa.Column(
            "booking_id",
            UUID(as_uuid=True),
            sa.ForeignKey("bookings.id", ondelete="SET NULL"),
        ),
        sa.Column("price_cents", sa.BigInteger(), nullable=False),
        sa.Column(
            "version",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "sailing_id",
            "cabin_id",
            name="uq_sailing_cabin",
        ),
    )

    op.create_index(
        "uq_inventory_booked",
        "cabin_inventory",
        ["sailing_id", "cabin_id"],
        unique=True,
        postgresql_where=sa.text("status = 'booked'"),
    )

    op.create_index(
        "ix_inventory_lookup",
        "cabin_inventory",
        ["sailing_id", "status"],
    )

    op.create_index(
        "ix_inventory_hold_expiry",
        "cabin_inventory",
        ["hold_expires_at"],
        postgresql_where=sa.text("status = 'held'"),
    )

    op.create_table(
        "booking_cabins",
        uid(),
        sa.Column(
            "booking_id",
            UUID(as_uuid=True),
            sa.ForeignKey("bookings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "cabin_inventory_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cabin_inventory.id"),
            nullable=False,
        ),
        sa.Column(
            "cabin_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cabins.id"),
            nullable=False,
        ),
        sa.Column("occupancy", sa.Integer(), nullable=False),
        sa.Column("price_cents", sa.BigInteger(), nullable=False),
        sa.UniqueConstraint("booking_id", "cabin_id"),
    )

    op.create_table(
        "booking_guests",
        uid(),
        sa.Column(
            "booking_id",
            UUID(as_uuid=True),
            sa.ForeignKey("bookings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "cabin_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cabins.id"),
            nullable=False,
        ),
        sa.Column("full_name", sa.String(160), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("gender", sa.String(40)),
        sa.Column("nationality", sa.String(100)),
        sa.Column("passport_number", sa.String(100)),
        sa.Column(
            "is_lead_guest",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )

    # -------------------------------------------------------------------------
    # PAYMENTS / REFUNDS
    # -------------------------------------------------------------------------

    op.create_table(
        "payments",
        uid(),
        sa.Column(
            "booking_id",
            UUID(as_uuid=True),
            sa.ForeignKey("bookings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "stripe_payment_intent_id",
            sa.String(255),
            unique=True,
            nullable=False,
        ),
        sa.Column("stripe_charge_id", sa.String(255)),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False),
        sa.Column(
            "status",
            enum("payment_status"),
            nullable=False,
        ),
        sa.Column("failure_reason", sa.Text()),
        sa.Column("raw_payload", JSONB),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "webhook_events",
        uid(),
        sa.Column(
            "stripe_event_id",
            sa.String(255),
            unique=True,
            nullable=False,
        ),
        sa.Column("event_type", sa.String(160), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "refund_policies",
        uid(),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column(
            "is_default",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
    )

    op.add_column(
        "cruises",
        sa.Column(
            "refund_policy_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "refund_policies.id",
                ondelete="SET NULL",
            ),
        ),
    )

    op.create_table(
        "refund_policy_rules",
        uid(),
        sa.Column(
            "policy_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "refund_policies.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "min_days_before_departure",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "max_days_before_departure",
            sa.Integer(),
        ),
        sa.Column(
            "refund_percent",
            sa.Numeric(5, 2),
            nullable=False,
        ),
        sa.Column(
            "flat_fee_cents",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
    )

    op.create_table(
        "cancellation_requests",
        uid(),
        sa.Column(
            "booking_id",
            UUID(as_uuid=True),
            sa.ForeignKey("bookings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "requested_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "status",
            enum("cancellation_status"),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "reviewed_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
        ),
        sa.Column("admin_note", sa.Text()),
        sa.Column("policy_snapshot", JSONB),
        sa.Column("calculated_refund_cents", sa.BigInteger()),
        sa.Column("final_refund_cents", sa.BigInteger()),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
    )

    op.create_index(
        "uq_open_cancel_request",
        "cancellation_requests",
        ["booking_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )

    op.create_table(
        "refunds",
        uid(),
        sa.Column(
            "booking_id",
            UUID(as_uuid=True),
            sa.ForeignKey("bookings.id"),
            nullable=False,
        ),
        sa.Column(
            "cancellation_request_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cancellation_requests.id"),
            nullable=False,
        ),
        sa.Column(
            "payment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("payments.id"),
            nullable=False,
        ),
        sa.Column(
            "stripe_refund_id",
            sa.String(255),
            unique=True,
        ),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            enum("refund_status"),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("failure_reason", sa.Text()),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
    )

    # -------------------------------------------------------------------------
    # SAVED CRUISES / NOTIFICATIONS / AUDIT
    # -------------------------------------------------------------------------

    op.create_table(
        "saved_cruises",
        uid(),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "cruise_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cruises.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sailing_id",
            UUID(as_uuid=True),
            sa.ForeignKey("sailings.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id",
            "cruise_id",
            "sailing_id",
        ),
    )

    op.create_index(
        "uq_saved_no_sailing",
        "saved_cruises",
        ["user_id", "cruise_id"],
        unique=True,
        postgresql_where=sa.text("sailing_id IS NULL"),
    )

    op.create_index(
        "uq_saved_with_sailing",
        "saved_cruises",
        ["user_id", "cruise_id", "sailing_id"],
        unique=True,
        postgresql_where=sa.text("sailing_id IS NOT NULL"),
    )

    op.create_table(
        "notifications",
        uid(),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "type",
            enum("notification_type"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("data", JSONB),
        sa.Column(
            "is_read",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column(
            "sent_push",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column(
            "sent_email",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_notifications_user",
        "notifications",
        ["user_id", "is_read", "created_at"],
    )

    op.create_table(
        "audit_logs",
        uid(),
        sa.Column(
            "actor_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("entity_type", sa.String(120), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True)),
        sa.Column("before", JSONB),
        sa.Column("after", JSONB),
        sa.Column("ip", sa.String(64)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "rate_limit_counters",
        sa.Column(
            "key",
            sa.String(255),
            primary_key=True,
        ),
        sa.Column(
            "window_start",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade():
    # For a development project, dropping the tables in reverse dependency
    # order is enough.

    op.drop_index(
        "uq_saved_with_sailing",
        table_name="saved_cruises",
    )

    op.drop_index(
        "uq_saved_no_sailing",
        table_name="saved_cruises",
    )

    op.drop_index(
        "ix_bookings_sailing",
        table_name="bookings",
    )

    op.drop_index(
        "ix_bookings_user",
        table_name="bookings",
    )

    for table_name in [
        "rate_limit_counters",
        "audit_logs",
        "notifications",
        "saved_cruises",
        "refunds",
        "cancellation_requests",
        "refund_policy_rules",
        "refund_policies",
        "webhook_events",
        "payments",
        "booking_guests",
        "booking_cabins",
        "cabin_inventory",
        "bookings",
        "cabins",
        "cabin_type_amenities",
        "amenities",
        "cabin_types",
        "decks",
        "sailings",
        "cruise_itineraries",
        "cruise_images",
        "cruises",
        "ports",
        "ships",
        "device_tokens",
        "otp_codes",
        "refresh_tokens",
        "users",
    ]:
        op.drop_table(table_name)

    # Drop the manually-created PostgreSQL ENUM types last.
    for enum_name in [
        "notification_type",
        "refund_status",
        "cancellation_status",
        "payment_status",
        "booking_status",
        "booking_channel",
        "inventory_status",
        "sailing_status",
        "approval_status",
        "cruise_status",
        "otp_purpose",
        "user_role",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")