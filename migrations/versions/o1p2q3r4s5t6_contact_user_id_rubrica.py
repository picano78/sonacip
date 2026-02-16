"""add user_id to contact for rubrica

Revision ID: o1p2q3r4s5t6
Revises: 5bd2c4382674
Create Date: 2026-02-16 10:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'o1p2q3r4s5t6'
down_revision = '5bd2c4382674'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('contact', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_contact_user_id', ['user_id'])
        batch_op.create_foreign_key('fk_contact_user_id', 'user', ['user_id'], ['id'])


def downgrade():
    with op.batch_alter_table('contact', schema=None) as batch_op:
        batch_op.drop_constraint('fk_contact_user_id', type_='foreignkey')
        batch_op.drop_index('ix_contact_user_id')
        batch_op.drop_column('user_id')
