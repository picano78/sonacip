"""society calendar event series fields

Revision ID: l8n9o0p1q2r3
Revises: k4m5n6p7q8r9
Create Date: 2026-02-11 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "l8n9o0p1q2r3"
down_revision = "k4m5n6p7q8r9"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("society_calendar_event", schema=None) as batch_op:
        batch_op.add_column(sa.Column("series_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("series_rule", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("series_until", sa.Date(), nullable=True))
        batch_op.create_index("ix_society_calendar_event_series_id", ["series_id"], unique=False)


def downgrade():
    with op.batch_alter_table("society_calendar_event", schema=None) as batch_op:
        batch_op.drop_index("ix_society_calendar_event_series_id")
        batch_op.drop_column("series_until")
        batch_op.drop_column("series_rule")
        batch_op.drop_column("series_id")

