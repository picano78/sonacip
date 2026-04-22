"""stripe billing fields

Revision ID: 3a4d9f0b2c21
Revises: 9f0c2b1a7d10
Create Date: 2026-02-01 20:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3a4d9f0b2c21"
down_revision = "9f0c2b1a7d10"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("plan", schema=None) as batch_op:
        batch_op.add_column(sa.Column("stripe_price_monthly_id", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("stripe_price_yearly_id", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("stripe_product_id", sa.String(length=120), nullable=True))

    with op.batch_alter_table("subscription", schema=None) as batch_op:
        batch_op.add_column(sa.Column("stripe_customer_id", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("stripe_subscription_id", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("cancel_at_period_end", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("current_period_end", sa.DateTime(), nullable=True))
        batch_op.create_index(batch_op.f("ix_subscription_stripe_customer_id"), ["stripe_customer_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_subscription_stripe_subscription_id"), ["stripe_subscription_id"], unique=False)


def downgrade():
    with op.batch_alter_table("subscription", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_subscription_stripe_subscription_id"))
        batch_op.drop_index(batch_op.f("ix_subscription_stripe_customer_id"))
        batch_op.drop_column("current_period_end")
        batch_op.drop_column("cancel_at_period_end")
        batch_op.drop_column("stripe_subscription_id")
        batch_op.drop_column("stripe_customer_id")

    with op.batch_alter_table("plan", schema=None) as batch_op:
        batch_op.drop_column("stripe_product_id")
        batch_op.drop_column("stripe_price_yearly_id")
        batch_op.drop_column("stripe_price_monthly_id")

