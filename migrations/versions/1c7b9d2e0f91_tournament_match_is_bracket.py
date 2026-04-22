"""tournament match is_bracket flag

Revision ID: 1c7b9d2e0f91
Revises: 6a1b2c3d4e55
Create Date: 2026-02-01 16:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1c7b9d2e0f91'
down_revision = '6a1b2c3d4e55'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tournament_match', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_bracket', sa.Boolean(), nullable=True, server_default=sa.text('FALSE')))
        batch_op.create_index(batch_op.f('ix_tournament_match_is_bracket'), ['is_bracket'], unique=False)


def downgrade():
    with op.batch_alter_table('tournament_match', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tournament_match_is_bracket'))
        batch_op.drop_column('is_bracket')

