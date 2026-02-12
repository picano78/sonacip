"""Add facility_id and color to Event model for field planner integration

Revision ID: add_event_field_planner_integration
Revises: 
Create Date: 2026-02-12 22:19:52.327000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_event_field_planner_integration'
down_revision = None  # Will be set by alembic when generated properly
branch_labels = None
depends_on = None


def upgrade():
    # Add facility_id and color columns to event table
    op.add_column('event', sa.Column('facility_id', sa.Integer(), nullable=True))
    op.add_column('event', sa.Column('color', sa.String(length=20), nullable=True, server_default='#212529'))
    
    # Create foreign key constraint
    op.create_foreign_key('fk_event_facility_id', 'event', 'facility', ['facility_id'], ['id'])
    
    # Create index on facility_id for better query performance
    op.create_index('ix_event_facility_id', 'event', ['facility_id'], unique=False)


def downgrade():
    # Drop index and foreign key constraint
    op.drop_index('ix_event_facility_id', table_name='event')
    op.drop_constraint('fk_event_facility_id', 'event', type_='foreignkey')
    
    # Drop columns
    op.drop_column('event', 'color')
    op.drop_column('event', 'facility_id')
