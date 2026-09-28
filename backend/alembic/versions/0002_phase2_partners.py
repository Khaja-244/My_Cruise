"""Phase 2 partner onboarding, API integration and commission metadata."""

from alembic import op
import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM

import uuid


revision = "0002_phase2_partners"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    # -------------------------------------------------------------------------
    # ENUM TYPES
    # -------------------------------------------------------------------------
    #
    # These ENUM types are created manually with CREATE TYPE.
    # Therefore, when they are used by table columns below, we must tell
    # SQLAlchemy not to create them again.
    #

    # Add the partner role to the existing user_role ENUM.
    op.execute(
        "ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'partner'"
    )

    # Partner account status.
    op.execute(
        "CREATE TYPE partner_status AS ENUM "
        "('pending','active','disabled','rejected')"
    )

    # Partner application review status.
    op.execute(
        "CREATE TYPE partner_application_status AS ENUM "
        "('pending','approved','rejected')"
    )

    # Commission calculation method.
    op.execute(
        "CREATE TYPE commission_type AS ENUM "
        "('percent','flat')"
    )

    # Partner integration connection status.
    op.execute(
        "CREATE TYPE integration_status AS ENUM "
        "('connected','suspended')"
    )

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def uid():
        """Create a standard UUID primary-key column."""
        return sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
        )

    def enum(name):
        """
        Reference an existing PostgreSQL ENUM type.

        The ENUM types are created explicitly above, so SQLAlchemy must not
        attempt to create them again when creating tables or columns.
        """
        return ENUM(
            name=name,
            create_type=False,
        )

    # -------------------------------------------------------------------------
    # PARTNERS
    # -------------------------------------------------------------------------

    op.create_table(
        "partners",
        uid(),
        sa.Column(
            "business_name",
            sa.String(200),
            nullable=False,
        ),
        sa.Column(
            "contact_name",
            sa.String(160),
            nullable=False,
        ),
        sa.Column(
            "email",
            sa.String(255),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "phone",
            sa.String(40),
        ),
        sa.Column(
            "status",
            enum("partner_status"),
            server_default="active",
            nullable=False,
        ),
        sa.Column(
            "integration_status",
            enum("integration_status"),
            server_default="suspended",
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

    # -------------------------------------------------------------------------
    # PARTNER APPLICATIONS
    # -------------------------------------------------------------------------

    op.create_table(
        "partner_applications",
        uid(),
        sa.Column(
            "applicant_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "business_name",
            sa.String(200),
            nullable=False,
        ),
        sa.Column(
            "contact_name",
            sa.String(160),
            nullable=False,
        ),
        sa.Column(
            "email",
            sa.String(255),
            nullable=False,
        ),
        sa.Column(
            "phone",
            sa.String(40),
        ),
        sa.Column(
            "documents",
            JSONB,
        ),
        sa.Column(
            "status",
            enum("partner_application_status"),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "reviewer_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
        ),
        sa.Column(
            "review_reason",
            sa.Text(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
        ),
    )

    # -------------------------------------------------------------------------
    # PARTNER API KEYS
    # -------------------------------------------------------------------------

    op.create_table(
        "partner_api_keys",
        uid(),
        sa.Column(
            "partner_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "partners.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "key_hash",
            sa.String(64),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "key_prefix",
            sa.String(20),
            nullable=False,
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.Column(
            "rate_limit_per_minute",
            sa.Integer(),
            server_default="60",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
        ),
    )

    op.create_index(
        "ix_partner_api_key_hash",
        "partner_api_keys",
        ["key_hash"],
    )

    # -------------------------------------------------------------------------
    # PARTNER WEBSITES
    # -------------------------------------------------------------------------

    op.create_table(
        "partner_websites",
        uid(),
        sa.Column(
            "partner_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "partners.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "name",
            sa.String(160),
            nullable=False,
        ),
        sa.Column(
            "website_url",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "integration_status",
            enum("integration_status"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # -------------------------------------------------------------------------
    # PARTNER CRUISE EXPOSURE
    # -------------------------------------------------------------------------

    op.create_table(
        "partner_cruise_exposures",
        uid(),
        sa.Column(
            "partner_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "partners.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "cruise_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "cruises.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.UniqueConstraint(
            "partner_id",
            "cruise_id",
            name="uq_partner_cruise_exposure",
        ),
    )

    # -------------------------------------------------------------------------
    # PARTNER API USAGE
    # -------------------------------------------------------------------------

    op.create_table(
        "partner_api_usage",
        uid(),
        sa.Column(
            "api_key_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "partner_api_keys.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "method",
            sa.String(10),
            nullable=False,
        ),
        sa.Column(
            "path",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "status_code",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "duration_ms",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # -------------------------------------------------------------------------
    # CRUISE PARTNER / COMMISSION FIELDS
    # -------------------------------------------------------------------------

    # Identifies whether the cruise belongs to the platform or a partner.
    op.add_column(
        "cruises",
        sa.Column(
            "owner_type",
            sa.String(20),
            server_default="platform",
            nullable=False,
        ),
    )

    # Commission calculation method.
    op.add_column(
        "cruises",
        sa.Column(
            "commission_type",
            enum("commission_type"),
        ),
    )

    # Commission value.
    #
    # Example:
    #   commission_type = "percent"
    #   commission_value = 10.00
    #
    # means a 10% commission.
    op.add_column(
        "cruises",
        sa.Column(
            "commission_value",
            sa.Numeric(12, 2),
        ),
    )

    # Faster lookup for partner-owned cruises filtered by approval status.
    op.create_index(
        "ix_cruises_partner_approval",
        "cruises",
        ["partner_id", "approval_status"],
    )


def downgrade():
    # -------------------------------------------------------------------------
    # REMOVE CRUISE COMMISSION FIELDS
    # -------------------------------------------------------------------------

    op.drop_index(
        "ix_cruises_partner_approval",
        table_name="cruises",
    )

    op.drop_column(
        "cruises",
        "commission_value",
    )

    op.drop_column(
        "cruises",
        "commission_type",
    )

    op.drop_column(
        "cruises",
        "owner_type",
    )

    # -------------------------------------------------------------------------
    # REMOVE PARTNER TABLES
    # -------------------------------------------------------------------------

    # Drop tables in reverse dependency order.
    for table_name in [
        "partner_api_usage",
        "partner_cruise_exposures",
        "partner_websites",
        "partner_api_keys",
        "partner_applications",
        "partners",
    ]:
        op.drop_table(table_name)

    # -------------------------------------------------------------------------
    # REMOVE ENUM TYPES
    # -------------------------------------------------------------------------

    op.execute(
        "DROP TYPE IF EXISTS integration_status"
    )

    op.execute(
        "DROP TYPE IF EXISTS commission_type"
    )

    op.execute(
        "DROP TYPE IF EXISTS partner_application_status"
    )

    op.execute(
        "DROP TYPE IF EXISTS partner_status"
    )