"""Add society planner notifications and live banners

Revision ID: add_society_export_banners
Revises: d2f4a6c8e0b1
Create Date: 2026-02-16 09:21:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_society_export_banners'
down_revision = 'd2f4a6c8e0b1'

def upgrade():
    # Add planner_notifications_enabled to society table
    op.add_column('society', sa.Column('planner_notifications_enabled', sa.Boolean(), nullable=True))
    # Set default value for existing rows
    op.execute("UPDATE society SET planner_notifications_enabled = TRUE WHERE planner_notifications_enabled IS NULL")
    
    # Create live_banner table
    op.create_table('live_banner',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('image_url', sa.String(length=500), nullable=True),
        sa.Column('link_url', sa.String(length=500), nullable=True),
        sa.Column('position', sa.String(length=20), nullable=True),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_live_banner_is_active'), 'live_banner', ['is_active'], unique=False)
    op.create_index(op.f('ix_live_banner_created_at'), 'live_banner', ['created_at'], unique=False)
    op.create_index(op.f('ix_live_banner_created_by'), 'live_banner', ['created_by'], unique=False)


def downgrade():
    # Drop live_banner table
    op.drop_index(op.f('ix_live_banner_created_by'), table_name='live_banner')
    op.drop_index(op.f('ix_live_banner_created_at'), table_name='live_banner')
    op.drop_index(op.f('ix_live_banner_is_active'), table_name='live_banner')
    op.drop_table('live_banner')
    
    # Remove planner_notifications_enabled from society
    op.drop_column('society', 'planner_notifications_enabled')
