"""whatsapp pro templates optin logs

Revision ID: e5f7a2b3c4d5
Revises: d4e6a1b0c2d3
Create Date: 2026-02-01 22:25:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e5f7a2b3c4d5"
down_revision = "d4e6a1b0c2d3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "whatsapp_template",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("provider_template_name", sa.String(length=200), nullable=False),
        sa.Column("language_code", sa.String(length=20), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("body_preview", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("key", name="uq_whatsapp_template_key"),
    )
    op.create_index("ix_whatsapp_template_key", "whatsapp_template", ["key"], unique=False)
    op.create_index("ix_whatsapp_template_created_at", "whatsapp_template", ["created_at"], unique=False)

    op.create_table(
        "whatsapp_optin",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("society_id", sa.Integer(), sa.ForeignKey("society.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("phone_number", sa.String(length=30), nullable=True),
        sa.Column("is_opted_in", sa.Boolean(), nullable=True),
        sa.Column("opted_in_at", sa.DateTime(), nullable=True),
        sa.Column("opted_out_at", sa.DateTime(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("society_id", "user_id", name="uq_whatsapp_optin_scope"),
    )
    op.create_index("ix_whatsapp_optin_society_id", "whatsapp_optin", ["society_id"], unique=False)
    op.create_index("ix_whatsapp_optin_user_id", "whatsapp_optin", ["user_id"], unique=False)
    op.create_index("ix_whatsapp_optin_created_at", "whatsapp_optin", ["created_at"], unique=False)

    op.create_table(
        "whatsapp_message_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("society_id", sa.Integer(), sa.ForeignKey("society.id"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("to_number", sa.String(length=30), nullable=True),
        sa.Column("template_key", sa.String(length=120), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("provider_response", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_whatsapp_message_log_society_id", "whatsapp_message_log", ["society_id"], unique=False)
    op.create_index("ix_whatsapp_message_log_user_id", "whatsapp_message_log", ["user_id"], unique=False)
    op.create_index("ix_whatsapp_message_log_created_at", "whatsapp_message_log", ["created_at"], unique=False)


def downgrade():
    op.drop_index("ix_whatsapp_message_log_created_at", table_name="whatsapp_message_log")
    op.drop_index("ix_whatsapp_message_log_user_id", table_name="whatsapp_message_log")
    op.drop_index("ix_whatsapp_message_log_society_id", table_name="whatsapp_message_log")
    op.drop_table("whatsapp_message_log")

    op.drop_index("ix_whatsapp_optin_created_at", table_name="whatsapp_optin")
    op.drop_index("ix_whatsapp_optin_user_id", table_name="whatsapp_optin")
    op.drop_index("ix_whatsapp_optin_society_id", table_name="whatsapp_optin")
    op.drop_table("whatsapp_optin")

    op.drop_index("ix_whatsapp_template_created_at", table_name="whatsapp_template")
    op.drop_index("ix_whatsapp_template_key", table_name="whatsapp_template")
    op.drop_table("whatsapp_template")

