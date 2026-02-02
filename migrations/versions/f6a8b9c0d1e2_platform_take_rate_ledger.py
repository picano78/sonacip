"""platform take rate ledger

Revision ID: f6a8b9c0d1e2
Revises: e5f7a2b3c4d5
Create Date: 2026-02-01 22:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f6a8b9c0d1e2"
down_revision = "e5f7a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "platform_fee_setting",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("take_rate_percent", sa.Integer(), nullable=True),
        sa.Column("min_fee_cents", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "platform_transaction",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("society_id", sa.Integer(), sa.ForeignKey("society.id"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payment.id"), nullable=True),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("gross_amount", sa.Float(), nullable=True),
        sa.Column("platform_fee_amount", sa.Float(), nullable=True),
        sa.Column("net_amount", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_platform_transaction_society_id", "platform_transaction", ["society_id"], unique=False)
    op.create_index("ix_platform_transaction_user_id", "platform_transaction", ["user_id"], unique=False)
    op.create_index("ix_platform_transaction_payment_id", "platform_transaction", ["payment_id"], unique=False)
    op.create_index("ix_platform_transaction_entity_id", "platform_transaction", ["entity_id"], unique=False)
    op.create_index("ix_platform_transaction_created_at", "platform_transaction", ["created_at"], unique=False)


def downgrade():
    op.drop_index("ix_platform_transaction_created_at", table_name="platform_transaction")
    op.drop_index("ix_platform_transaction_entity_id", table_name="platform_transaction")
    op.drop_index("ix_platform_transaction_payment_id", table_name="platform_transaction")
    op.drop_index("ix_platform_transaction_user_id", table_name="platform_transaction")
    op.drop_index("ix_platform_transaction_society_id", table_name="platform_transaction")
    op.drop_table("platform_transaction")
    op.drop_table("platform_fee_setting")

