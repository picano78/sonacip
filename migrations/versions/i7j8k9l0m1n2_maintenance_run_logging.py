"""maintenance run logging

Revision ID: i7j8k9l0m1n2
Revises: h1i2j3k4l5m6
Create Date: 2026-02-01 23:55:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "i7j8k9l0m1n2"
down_revision = "h1i2j3k4l5m6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "maintenance_run",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_type", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_maintenance_run_started_at", "maintenance_run", ["started_at"], unique=False)


def downgrade():
    op.drop_index("ix_maintenance_run_started_at", table_name="maintenance_run")
    op.drop_table("maintenance_run")

