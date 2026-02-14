"""add_link_preview_fields

Revision ID: m6n7o8p9q0r1
Revises: l5m6n7p8q9r0
Create Date: 2026-02-14 18:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'm6n7o8p9q0r1'
down_revision = 'l5m6n7p8q9r0'
branch_labels = None
depends_on = None


def upgrade():
    # Add link preview fields to post table
    op.add_column('post', sa.Column('link_url', sa.String(500), nullable=True))
    op.add_column('post', sa.Column('link_title', sa.String(255), nullable=True))
    op.add_column('post', sa.Column('link_description', sa.Text(), nullable=True))
    op.add_column('post', sa.Column('link_image', sa.String(500), nullable=True))
    op.add_column('post', sa.Column('link_provider', sa.String(50), nullable=True))


def downgrade():
    # Remove link preview fields from post table
    op.drop_column('post', 'link_provider')
    op.drop_column('post', 'link_image')
    op.drop_column('post', 'link_description')
    op.drop_column('post', 'link_title')
    op.drop_column('post', 'link_url')
