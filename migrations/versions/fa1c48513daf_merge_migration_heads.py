"""Merge migration heads

Revision ID: fa1c48513daf
Revises: 1221257e6c86, add_event_field_planner_integration, f1a2b3c4d5e6
Create Date: 2026-02-13 12:31:59.528289

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fa1c48513daf'
down_revision = ('1221257e6c86', 'add_event_field_planner_integration', 'f1a2b3c4d5e6')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
