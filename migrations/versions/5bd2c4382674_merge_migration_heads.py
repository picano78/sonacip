"""Merge migration heads

Revision ID: 5bd2c4382674
Revises: a1b2c3d4e5f6, e1f2a3b4c5d6, add_role_name_index, m6n7o8p9q0r1
Create Date: 2026-02-14 19:14:42.831636

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5bd2c4382674'
down_revision = ('a1b2c3d4e5f6', 'e1f2a3b4c5d6', 'add_role_name_index', 'm6n7o8p9q0r1')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
