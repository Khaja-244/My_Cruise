"""Complete Phase 2 partner workflow, ownership, booking identity and auditability."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0003_phase2_integrity'
down_revision = '0002_phase2_partners'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('partners', sa.Column('user_id', UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_partners_user_id', 'partners', 'users', ['user_id'], ['id'], ondelete='SET NULL')
    op.create_unique_constraint('uq_partners_user_id', 'partners', ['user_id'])
    op.execute("UPDATE partners p SET user_id = u.id FROM users u WHERE p.user_id IS NULL AND lower(p.email)=lower(u.email)")

    op.add_column('ships', sa.Column('owner_type', sa.String(20), server_default='platform', nullable=False))
    op.add_column('ships', sa.Column('partner_id', UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_ships_partner_id', 'ships', 'partners', ['partner_id'], ['id'], ondelete='SET NULL')

    op.create_foreign_key('fk_cruises_partner_id', 'cruises', 'partners', ['partner_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_bookings_partner_id', 'bookings', 'partners', ['partner_id'], ['id'], ondelete='SET NULL')

    op.add_column('bookings', sa.Column('customer_name', sa.String(160), nullable=True))
    op.add_column('bookings', sa.Column('customer_email', sa.String(255), nullable=True))
    op.add_column('bookings', sa.Column('customer_phone', sa.String(40), nullable=True))

    op.add_column('partner_websites', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.add_column('partner_websites', sa.Column('last_connected_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_partner_api_usage_key_created', 'partner_api_usage', ['api_key_id', 'created_at'])

def downgrade():
    op.drop_index('ix_partner_api_usage_key_created', table_name='partner_api_usage')
    op.drop_column('partner_websites', 'last_connected_at')
    op.drop_column('partner_websites', 'updated_at')
    op.drop_column('bookings', 'customer_phone')
    op.drop_column('bookings', 'customer_email')
    op.drop_column('bookings', 'customer_name')
    op.drop_constraint('fk_bookings_partner_id', 'bookings', type_='foreignkey')
    op.drop_constraint('fk_cruises_partner_id', 'cruises', type_='foreignkey')
    op.drop_constraint('fk_ships_partner_id', 'ships', type_='foreignkey')
    op.drop_column('ships', 'partner_id')
    op.drop_column('ships', 'owner_type')
    op.drop_constraint('uq_partners_user_id', 'partners', type_='unique')
    op.drop_constraint('fk_partners_user_id', 'partners', type_='foreignkey')
    op.drop_column('partners', 'user_id')
