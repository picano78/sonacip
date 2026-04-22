"""Add members_year_end_policy to society

Revision ID: n8o9p0q1r2s3
Revises:
Create Date: 2026-02-16 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'n8o9p0q1r2s3'
down_revision = None  # Will be set to the latest revision when deployed
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('society', schema=None) as batch_op:
        batch_op.add_column(sa.Column('members_year_end_policy', sa.String(20), nullable=True))

    # Set default values for existing rows
    op.execute("UPDATE society SET members_year_end_policy = 'keep' WHERE members_year_end_policy IS NULL")

    with op.batch_alter_table('society', schema=None) as batch_op:
        batch_op.alter_column('members_year_end_policy', nullable=False)


def downgrade():
    with op.batch_alter_table('society', schema=None) as batch_op:
        batch_op.drop_column('members_year_end_policy')
