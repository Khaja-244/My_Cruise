"""Allow partner cruise exposure to be controlled per partner website."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0004_website_scoped_exposure'
down_revision = '0003_phase2_integrity'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('partner_cruise_exposures', sa.Column('partner_website_id', UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_partner_cruise_exposures_website',
        'partner_cruise_exposures', 'partner_websites',
        ['partner_website_id'], ['id'], ondelete='CASCADE'
    )
    op.drop_constraint('uq_partner_cruise_exposure', 'partner_cruise_exposures', type_='unique')
    op.create_unique_constraint(
        'uq_partner_website_cruise_exposure',
        'partner_cruise_exposures', ['partner_website_id', 'cruise_id']
    )
    op.create_index('uq_partner_cruise_legacy_exposure', 'partner_cruise_exposures', ['partner_id','cruise_id'], unique=True, postgresql_where=sa.text('partner_website_id IS NULL'))
    # Existing partner-level exposures remain valid. If a partner has exactly
    # one website, copy the exposure to that website so the new model is useful
    # immediately without changing existing API behaviour.
    op.execute("""
        INSERT INTO partner_cruise_exposures (id, partner_id, partner_website_id, cruise_id, enabled)
        SELECT gen_random_uuid(), e.partner_id, w.id, e.cruise_id, e.enabled
        FROM partner_cruise_exposures e
        JOIN partner_websites w ON w.partner_id = e.partner_id
        WHERE e.partner_website_id IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM partner_websites w2
              WHERE w2.partner_id = e.partner_id AND w2.id <> w.id
          )
    """)


def downgrade():
    op.drop_index('uq_partner_cruise_legacy_exposure', table_name='partner_cruise_exposures')
    op.drop_constraint('uq_partner_website_cruise_exposure', 'partner_cruise_exposures', type_='unique')
    op.create_unique_constraint('uq_partner_cruise_exposure', 'partner_cruise_exposures', ['partner_id','cruise_id'])
    op.drop_constraint('fk_partner_cruise_exposures_website', 'partner_cruise_exposures', type_='foreignkey')
    op.drop_column('partner_cruise_exposures', 'partner_website_id')
