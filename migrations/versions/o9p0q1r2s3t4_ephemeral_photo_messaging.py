"""Add ephemeral photo messaging fields

Revision ID: o9p0q1r2s3t4
Revises: n8o9p0q1r2s3
Create Date: 2026-02-16 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'o9p0q1r2s3t4'
down_revision = 'n8o9p0q1r2s3'
branch_labels = None
depends_on = None


def upgrade():
    # Add expires_at to message_attachment for ephemeral photo support
    with op.batch_alter_table('message_attachment', schema=None) as batch_op:
        batch_op.add_column(sa.Column('expires_at', sa.DateTime(), nullable=True))
        batch_op.create_index('ix_message_attachment_expires_at', ['expires_at'])

    # Add photo fields to message_group_message for group ephemeral photos
    with op.batch_alter_table('message_group_message', schema=None) as batch_op:
        batch_op.add_column(sa.Column('photo_path', sa.String(500), nullable=True))
        batch_op.add_column(sa.Column('photo_expires_at', sa.DateTime(), nullable=True))
        batch_op.create_index('ix_message_group_message_photo_expires_at', ['photo_expires_at'])


def downgrade():
    with op.batch_alter_table('message_group_message', schema=None) as batch_op:
        batch_op.drop_index('ix_message_group_message_photo_expires_at')
        batch_op.drop_column('photo_expires_at')
        batch_op.drop_column('photo_path')

    with op.batch_alter_table('message_attachment', schema=None) as batch_op:
        batch_op.drop_index('ix_message_attachment_expires_at')
        batch_op.drop_column('expires_at')
