"""Add durable refund-failed notification type."""
from alembic import op
revision = "0005_notification_refund_failed"
down_revision = "0004_website_scoped_exposure"
branch_labels = None
depends_on = None
def upgrade():
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'refund_failed'")
def downgrade():
    pass
