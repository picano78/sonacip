"""retention onboarding suggestions

Revision ID: c3d8f9a1e2b4
Revises: b7c1a8d2e4f0
Create Date: 2026-02-01 21:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c3d8f9a1e2b4"
down_revision = "b7c1a8d2e4f0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "society_health_snapshot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("society_id", sa.Integer(), sa.ForeignKey("society.id"), nullable=False),
        sa.Column("week_key", sa.String(length=12), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("society_id", "week_key", name="uq_society_health_snapshot_week"),
    )
    op.create_index("ix_society_health_snapshot_society_id", "society_health_snapshot", ["society_id"], unique=False)
    op.create_index("ix_society_health_snapshot_week_key", "society_health_snapshot", ["week_key"], unique=False)
    op.create_index("ix_society_health_snapshot_created_at", "society_health_snapshot", ["created_at"], unique=False)

    op.create_table(
        "user_onboarding_step",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("society_id", sa.Integer(), sa.ForeignKey("society.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("step_key", sa.String(length=80), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("society_id", "user_id", "step_key", name="uq_user_onboarding_step"),
    )
    op.create_index("ix_user_onboarding_step_society_id", "user_onboarding_step", ["society_id"], unique=False)
    op.create_index("ix_user_onboarding_step_user_id", "user_onboarding_step", ["user_id"], unique=False)
    op.create_index("ix_user_onboarding_step_step_key", "user_onboarding_step", ["step_key"], unique=False)
    op.create_index("ix_user_onboarding_step_completed_at", "user_onboarding_step", ["completed_at"], unique=False)

    op.create_table(
        "society_suggestion_dismissal",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("society_id", sa.Integer(), sa.ForeignKey("society.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("dismissed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("society_id", "user_id", "key", name="uq_society_suggestion_dismissal"),
    )
    op.create_index("ix_society_suggestion_dismissal_society_id", "society_suggestion_dismissal", ["society_id"], unique=False)
    op.create_index("ix_society_suggestion_dismissal_user_id", "society_suggestion_dismissal", ["user_id"], unique=False)
    op.create_index("ix_society_suggestion_dismissal_key", "society_suggestion_dismissal", ["key"], unique=False)
    op.create_index("ix_society_suggestion_dismissal_dismissed_at", "society_suggestion_dismissal", ["dismissed_at"], unique=False)


def downgrade():
    op.drop_index("ix_society_suggestion_dismissal_dismissed_at", table_name="society_suggestion_dismissal")
    op.drop_index("ix_society_suggestion_dismissal_key", table_name="society_suggestion_dismissal")
    op.drop_index("ix_society_suggestion_dismissal_user_id", table_name="society_suggestion_dismissal")
    op.drop_index("ix_society_suggestion_dismissal_society_id", table_name="society_suggestion_dismissal")
    op.drop_table("society_suggestion_dismissal")

    op.drop_index("ix_user_onboarding_step_completed_at", table_name="user_onboarding_step")
    op.drop_index("ix_user_onboarding_step_step_key", table_name="user_onboarding_step")
    op.drop_index("ix_user_onboarding_step_user_id", table_name="user_onboarding_step")
    op.drop_index("ix_user_onboarding_step_society_id", table_name="user_onboarding_step")
    op.drop_table("user_onboarding_step")

    op.drop_index("ix_society_health_snapshot_created_at", table_name="society_health_snapshot")
    op.drop_index("ix_society_health_snapshot_week_key", table_name="society_health_snapshot")
    op.drop_index("ix_society_health_snapshot_society_id", table_name="society_health_snapshot")
    op.drop_table("society_health_snapshot")

