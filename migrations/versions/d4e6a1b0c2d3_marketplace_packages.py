"""marketplace packages

Revision ID: d4e6a1b0c2d3
Revises: c3d8f9a1e2b4
Create Date: 2026-02-01 22:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d4e6a1b0c2d3"
down_revision = "c3d8f9a1e2b4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "marketplace_package",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_one_time", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("stripe_price_one_time_id", sa.String(length=120), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("slug", name="uq_marketplace_package_slug"),
    )
    op.create_index("ix_marketplace_package_slug", "marketplace_package", ["slug"], unique=False)
    op.create_index("ix_marketplace_package_created_at", "marketplace_package", ["created_at"], unique=False)

    op.create_table(
        "marketplace_package_item",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("marketplace_package.id"), nullable=False),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("template.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_marketplace_package_item_package_id", "marketplace_package_item", ["package_id"], unique=False)
    op.create_index("ix_marketplace_package_item_template_id", "marketplace_package_item", ["template_id"], unique=False)
    op.create_index("ix_marketplace_package_item_created_at", "marketplace_package_item", ["created_at"], unique=False)

    op.create_table(
        "marketplace_purchase",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("marketplace_package.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("society_id", sa.Integer(), sa.ForeignKey("society.id"), nullable=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payment.id"), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("installed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("package_id", "society_id", "user_id", name="uq_marketplace_purchase_scope_package"),
    )
    op.create_index("ix_marketplace_purchase_package_id", "marketplace_purchase", ["package_id"], unique=False)
    op.create_index("ix_marketplace_purchase_user_id", "marketplace_purchase", ["user_id"], unique=False)
    op.create_index("ix_marketplace_purchase_society_id", "marketplace_purchase", ["society_id"], unique=False)
    op.create_index("ix_marketplace_purchase_payment_id", "marketplace_purchase", ["payment_id"], unique=False)
    op.create_index("ix_marketplace_purchase_created_at", "marketplace_purchase", ["created_at"], unique=False)


def downgrade():
    op.drop_index("ix_marketplace_purchase_created_at", table_name="marketplace_purchase")
    op.drop_index("ix_marketplace_purchase_payment_id", table_name="marketplace_purchase")
    op.drop_index("ix_marketplace_purchase_society_id", table_name="marketplace_purchase")
    op.drop_index("ix_marketplace_purchase_user_id", table_name="marketplace_purchase")
    op.drop_index("ix_marketplace_purchase_package_id", table_name="marketplace_purchase")
    op.drop_table("marketplace_purchase")

    op.drop_index("ix_marketplace_package_item_created_at", table_name="marketplace_package_item")
    op.drop_index("ix_marketplace_package_item_template_id", table_name="marketplace_package_item")
    op.drop_index("ix_marketplace_package_item_package_id", table_name="marketplace_package_item")
    op.drop_table("marketplace_package_item")

    op.drop_index("ix_marketplace_package_created_at", table_name="marketplace_package")
    op.drop_index("ix_marketplace_package_slug", table_name="marketplace_package")
    op.drop_table("marketplace_package")

