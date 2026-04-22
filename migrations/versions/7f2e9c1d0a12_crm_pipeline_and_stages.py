"""crm pipeline and stages

Revision ID: 7f2e9c1d0a12
Revises: 2d6c1a4b9f20
Create Date: 2026-02-01 19:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7f2e9c1d0a12"
down_revision = "2d6c1a4b9f20"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "crm_pipeline",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("society_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], name="fk_crm_pipeline_created_by"),
        sa.ForeignKeyConstraint(["society_id"], ["society.id"], name="fk_crm_pipeline_society"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("society_id", name="uq_crm_pipeline_society"),
    )
    with op.batch_alter_table("crm_pipeline", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_crm_pipeline_created_at"), ["created_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_crm_pipeline_society_id"), ["society_id"], unique=False)

    op.create_table(
        "crm_pipeline_stage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pipeline_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("color", sa.String(length=20), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("is_won", sa.Boolean(), nullable=True),
        sa.Column("is_lost", sa.Boolean(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], name="fk_crm_pipeline_stage_created_by"),
        sa.ForeignKeyConstraint(["pipeline_id"], ["crm_pipeline.id"], name="fk_crm_pipeline_stage_pipeline"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pipeline_id", "key", name="uq_crm_pipeline_stage_key"),
    )
    with op.batch_alter_table("crm_pipeline_stage", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_crm_pipeline_stage_created_at"), ["created_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_crm_pipeline_stage_pipeline_id"), ["pipeline_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_crm_pipeline_stage_position"), ["position"], unique=False)


def downgrade():
    with op.batch_alter_table("crm_pipeline_stage", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_crm_pipeline_stage_position"))
        batch_op.drop_index(batch_op.f("ix_crm_pipeline_stage_pipeline_id"))
        batch_op.drop_index(batch_op.f("ix_crm_pipeline_stage_created_at"))
    op.drop_table("crm_pipeline_stage")

    with op.batch_alter_table("crm_pipeline", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_crm_pipeline_society_id"))
        batch_op.drop_index(batch_op.f("ix_crm_pipeline_created_at"))
    op.drop_table("crm_pipeline")

