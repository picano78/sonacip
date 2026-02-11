"""admin billing and broadcast tables

Revision ID: j2a4b6c8d0e1
Revises: i7j8k9l0m1n2, fcec1bf08c43
Create Date: 2026-02-08 10:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "j2a4b6c8d0e1"
down_revision = ("i7j8k9l0m1n2", "fcec1bf08c43")
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "platform_feature",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("icon", sa.String(length=60), nullable=True),
        sa.Column("is_premium", sa.Boolean(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.UniqueConstraint("key", name="uq_platform_feature_key"),
    )
    op.create_index("ix_platform_feature_key", "platform_feature", ["key"], unique=False)

    op.create_table(
        "promotion_tier",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=60), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("icon", sa.String(length=60), nullable=True),
        sa.Column("color", sa.String(length=7), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=True),
        sa.Column("stripe_price_id", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.UniqueConstraint("slug", name="uq_promotion_tier_slug"),
    )
    op.create_index("ix_promotion_tier_slug", "promotion_tier", ["slug"], unique=False)

    op.create_table(
        "listing_promotion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("marketplace_listing.id"), nullable=False),
        sa.Column("tier_id", sa.Integer(), sa.ForeignKey("promotion_tier.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payment.id"), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("starts_at", sa.DateTime(), nullable=True),
        sa.Column("ends_at", sa.DateTime(), nullable=True),
        sa.Column("amount_paid", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_listing_promotion_listing_id", "listing_promotion", ["listing_id"], unique=False)
    op.create_index("ix_listing_promotion_user_id", "listing_promotion", ["user_id"], unique=False)
    op.create_index("ix_listing_promotion_status", "listing_promotion", ["status"], unique=False)

    op.create_table(
        "platform_payment_setting",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stripe_enabled", sa.Boolean(), nullable=True),
        sa.Column("stripe_account_id", sa.String(length=120), nullable=True),
        sa.Column("bank_account_holder", sa.String(length=200), nullable=True),
        sa.Column("bank_name", sa.String(length=200), nullable=True),
        sa.Column("bank_iban", sa.String(length=60), nullable=True),
        sa.Column("bank_bic_swift", sa.String(length=30), nullable=True),
        sa.Column("bank_country", sa.String(length=60), nullable=True),
        sa.Column("paypal_email", sa.String(length=200), nullable=True),
        sa.Column("payout_method", sa.String(length=30), nullable=True),
        sa.Column("payout_frequency", sa.String(length=20), nullable=True),
        sa.Column("min_payout_amount", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "broadcast_message",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("scope_type", sa.String(length=20), nullable=False),
        sa.Column("society_id", sa.Integer(), sa.ForeignKey("society.id"), nullable=True),
        sa.Column("subject", sa.String(length=300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("target_roles", sa.Text(), nullable=True),
        sa.Column("send_email", sa.Boolean(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("total_recipients", sa.Integer(), nullable=True),
        sa.Column("total_read", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_broadcast_message_sender_id", "broadcast_message", ["sender_id"], unique=False)
    op.create_index("ix_broadcast_message_society_id", "broadcast_message", ["society_id"], unique=False)

    op.create_table(
        "broadcast_recipient",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("broadcast_id", sa.Integer(), sa.ForeignKey("broadcast_message.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("message.id"), nullable=True),
        sa.Column("delivery_status", sa.String(length=20), nullable=True),
        sa.Column("email_sent", sa.Boolean(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("broadcast_id", "user_id", name="uq_broadcast_recipient"),
    )
    op.create_index("ix_broadcast_recipient_broadcast_id", "broadcast_recipient", ["broadcast_id"], unique=False)
    op.create_index("ix_broadcast_recipient_user_id", "broadcast_recipient", ["user_id"], unique=False)


def downgrade():
    op.drop_index("ix_broadcast_recipient_user_id", table_name="broadcast_recipient")
    op.drop_index("ix_broadcast_recipient_broadcast_id", table_name="broadcast_recipient")
    op.drop_table("broadcast_recipient")

    op.drop_index("ix_broadcast_message_society_id", table_name="broadcast_message")
    op.drop_index("ix_broadcast_message_sender_id", table_name="broadcast_message")
    op.drop_table("broadcast_message")

    op.drop_table("platform_payment_setting")

    op.drop_index("ix_listing_promotion_status", table_name="listing_promotion")
    op.drop_index("ix_listing_promotion_user_id", table_name="listing_promotion")
    op.drop_index("ix_listing_promotion_listing_id", table_name="listing_promotion")
    op.drop_table("listing_promotion")

    op.drop_index("ix_promotion_tier_slug", table_name="promotion_tier")
    op.drop_table("promotion_tier")

    op.drop_index("ix_platform_feature_key", table_name="platform_feature")
    op.drop_table("platform_feature")
