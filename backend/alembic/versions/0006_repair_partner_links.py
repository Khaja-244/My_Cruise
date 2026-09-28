"""Repair legacy partner applications that point to the wrong user account."""
from alembic import op

revision = "0006_repair_partner_links"
down_revision = "0005_notification_refund_failed"
branch_labels = None
depends_on = None


def upgrade():
    # Older builds accepted any email in PartnerApplicationCreate while storing
    # applicant_user_id from the authenticated token. Repair rows where the
    # submitted application email identifies an existing user account.
    op.execute(
        """
        UPDATE partner_applications pa
        SET applicant_user_id = u.id,
            email = lower(trim(u.email::text))
        FROM users u
        WHERE lower(trim(pa.email)) = lower(trim(u.email::text))
          AND (pa.applicant_user_id IS NULL OR pa.applicant_user_id <> u.id)
        """
    )

    # Normalize application emails for deterministic comparisons going forward.
    op.execute(
        """
        UPDATE partner_applications
        SET email = lower(trim(email))
        WHERE email <> lower(trim(email))
        """
    )


def downgrade():
    # Data repair is intentionally irreversible; no safe downgrade exists.
    pass
