"""Add FieldPlannerEvent model for field planner

Revision ID: l5m6n7p8q9r0
Revises: k4m5n6p7q8r9
Create Date: 2026-02-14 08:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "l5m6n7p8q9r0"
down_revision = "k4m5n6p7q8r9"
branch_labels = None
depends_on = None


def upgrade():
    # Create field_planner_event table
    op.create_table(
        "field_planner_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("society_id", sa.Integer(), nullable=False),
        sa.Column("facility_id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("team", sa.String(length=100), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("start_datetime", sa.DateTime(), nullable=False),
        sa.Column("end_datetime", sa.DateTime(), nullable=False),
        sa.Column("is_recurring", sa.Boolean(), nullable=True),
        sa.Column("recurrence_pattern", sa.String(length=50), nullable=True),
        sa.Column("recurrence_end_date", sa.Date(), nullable=True),
        sa.Column("parent_event_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("color", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
        sa.ForeignKeyConstraint(["facility_id"], ["facility.id"]),
        sa.ForeignKeyConstraint(["parent_event_id"], ["field_planner_event.id"]),
        sa.ForeignKeyConstraint(["society_id"], ["society.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    
    # Create indexes
    with op.batch_alter_table("field_planner_event", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_field_planner_event_society_id"), ["society_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_field_planner_event_facility_id"), ["facility_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_field_planner_event_start_datetime"), ["start_datetime"], unique=False)


def downgrade():
    op.drop_table("field_planner_event")
