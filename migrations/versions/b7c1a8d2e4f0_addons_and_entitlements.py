"""addons and entitlements

Revision ID: b7c1a8d2e4f0
Revises: 3a4d9f0b2c21
Create Date: 2026-02-01 21:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b7c1a8d2e4f0"
down_revision = "3a4d9f0b2c21"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "addon",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("feature_key", sa.String(length=80), nullable=False),
        sa.Column("price_one_time", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("stripe_price_one_time_id", sa.String(length=120), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("slug", name="uq_addon_slug"),
    )
    op.create_index("ix_addon_slug", "addon", ["slug"], unique=False)
    op.create_index("ix_addon_feature_key", "addon", ["feature_key"], unique=False)
    op.create_index("ix_addon_created_at", "addon", ["created_at"], unique=False)

    op.create_table(
        "addon_entitlement",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("addon_id", sa.Integer(), sa.ForeignKey("addon.id"), nullable=False),
        sa.Column("feature_key", sa.String(length=80), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("society_id", sa.Integer(), sa.ForeignKey("society.id"), nullable=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payment.id"), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("start_date", sa.DateTime(), nullable=True),
        sa.Column("end_date", sa.DateTime(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_addon_entitlement_addon_id", "addon_entitlement", ["addon_id"], unique=False)
    op.create_index("ix_addon_entitlement_feature_key", "addon_entitlement", ["feature_key"], unique=False)
    op.create_index("ix_addon_entitlement_user_id", "addon_entitlement", ["user_id"], unique=False)
    op.create_index("ix_addon_entitlement_society_id", "addon_entitlement", ["society_id"], unique=False)
    op.create_index("ix_addon_entitlement_payment_id", "addon_entitlement", ["payment_id"], unique=False)
    op.create_index("ix_addon_entitlement_start_date", "addon_entitlement", ["start_date"], unique=False)
    op.create_index("ix_addon_entitlement_created_at", "addon_entitlement", ["created_at"], unique=False)


def downgrade():
    op.drop_index("ix_addon_entitlement_created_at", table_name="addon_entitlement")
    op.drop_index("ix_addon_entitlement_start_date", table_name="addon_entitlement")
    op.drop_index("ix_addon_entitlement_payment_id", table_name="addon_entitlement")
    op.drop_index("ix_addon_entitlement_society_id", table_name="addon_entitlement")
    op.drop_index("ix_addon_entitlement_user_id", table_name="addon_entitlement")
    op.drop_index("ix_addon_entitlement_feature_key", table_name="addon_entitlement")
    op.drop_index("ix_addon_entitlement_addon_id", table_name="addon_entitlement")
    op.drop_table("addon_entitlement")

    op.drop_index("ix_addon_created_at", table_name="addon")
    op.drop_index("ix_addon_feature_key", table_name="addon")
    op.drop_index("ix_addon_slug", table_name="addon")
    op.drop_table("addon")

