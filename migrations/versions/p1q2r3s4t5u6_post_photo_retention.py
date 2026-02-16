"""Add photo retention settings and post photo expiration

Revision ID: p1q2r3s4t5u6
Revises: o9p0q1r2s3t4
Create Date: 2026-02-16 12:22:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'p1q2r3s4t5u6'
down_revision = 'o9p0q1r2s3t4'
branch_labels = None
depends_on = None


def upgrade():
    # Add photo_retention_hours to social_setting (0 = forever)
    with op.batch_alter_table('social_setting', schema=None) as batch_op:
        batch_op.add_column(sa.Column('photo_retention_hours', sa.Integer(), nullable=True, server_default='0'))

    # Add photo_expires_at to post for auto-deletion tracking
    with op.batch_alter_table('post', schema=None) as batch_op:
        batch_op.add_column(sa.Column('photo_expires_at', sa.DateTime(), nullable=True))
        batch_op.create_index('ix_post_photo_expires_at', ['photo_expires_at'])


def downgrade():
    with op.batch_alter_table('post', schema=None) as batch_op:
        batch_op.drop_index('ix_post_photo_expires_at')
        batch_op.drop_column('photo_expires_at')

    with op.batch_alter_table('social_setting', schema=None) as batch_op:
        batch_op.drop_column('photo_retention_hours')
