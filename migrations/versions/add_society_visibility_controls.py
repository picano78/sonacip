"""Add visibility controls to SocietyMembership

Revision ID: f1a2b3c4d5e6
Revises: 
Create Date: 2026-02-13 11:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = None  # Will be set to the latest revision when deployed
branch_labels = None
depends_on = None


def upgrade():
    # Add visibility and permission control columns to society_membership
    with op.batch_alter_table('society_membership', schema=None) as batch_op:
        batch_op.add_column(sa.Column('can_see_all_events', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('can_manage_planner', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('receive_planner_notifications', sa.Boolean(), nullable=True))
    
    # Set default values for existing rows
    op.execute("""
        UPDATE society_membership 
        SET can_see_all_events = CASE 
            WHEN role_name IN ('dirigente', 'coach', 'staff') THEN 1
            ELSE 0
        END,
        can_manage_planner = CASE 
            WHEN role_name IN ('dirigente', 'coach') THEN 1
            ELSE 0
        END,
        receive_planner_notifications = 1
        WHERE can_see_all_events IS NULL
    """)
    
    # Make columns non-nullable after setting defaults
    with op.batch_alter_table('society_membership', schema=None) as batch_op:
        batch_op.alter_column('can_see_all_events', nullable=False)
        batch_op.alter_column('can_manage_planner', nullable=False)
        batch_op.alter_column('receive_planner_notifications', nullable=False)


def downgrade():
    # Remove the visibility control columns
    with op.batch_alter_table('society_membership', schema=None) as batch_op:
        batch_op.drop_column('receive_planner_notifications')
        batch_op.drop_column('can_manage_planner')
        batch_op.drop_column('can_see_all_events')
