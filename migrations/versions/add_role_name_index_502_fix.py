"""add index on role.name to fix 502 registration timeouts

Revision ID: add_role_name_index
Revises: 78b7221f7c74
Create Date: 2026-02-14 17:30:00.000000

This migration adds a critical database index on the role.name column
to fix 502 Bad Gateway errors during user and society registration.

Without this index, the Role.query.filter_by(name=role_name).first()
lookup in registration endpoints performs a full table scan, which
can cause slow queries that exceed gunicorn's timeout threshold.

The index ensures O(1) lookups instead of O(n), dramatically improving
registration performance and preventing timeout errors.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_role_name_index'
down_revision = '78b7221f7c74'
branch_labels = None
depends_on = None


def upgrade():
    # Add index on role.name for faster lookups during registration
    # This is critical for preventing 502 timeouts
    with op.batch_alter_table('role', schema=None) as batch_op:
        batch_op.create_index('idx_role_name', ['name'], unique=False)


def downgrade():
    # Remove the index if rolling back
    with op.batch_alter_table('role', schema=None) as batch_op:
        batch_op.drop_index('idx_role_name')
