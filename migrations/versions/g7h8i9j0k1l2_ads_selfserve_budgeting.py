"""ads selfserve budgeting

Revision ID: g7h8i9j0k1l2
Revises: f6a8b9c0d1e2
Create Date: 2026-02-01 23:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "g7h8i9j0k1l2"
down_revision = "f6a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("ad_campaign", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_self_serve", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("advertiser_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("budget_cents", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("spend_cents", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_ad_campaign_is_self_serve"), ["is_self_serve"], unique=False)
        batch_op.create_index(batch_op.f("ix_ad_campaign_advertiser_user_id"), ["advertiser_user_id"], unique=False)
        batch_op.create_foreign_key("fk_ad_campaign_advertiser_user_id", "user", ["advertiser_user_id"], ["id"])


def downgrade():
    with op.batch_alter_table("ad_campaign", schema=None) as batch_op:
        batch_op.drop_constraint("fk_ad_campaign_advertiser_user_id", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_ad_campaign_advertiser_user_id"))
        batch_op.drop_index(batch_op.f("ix_ad_campaign_is_self_serve"))
        batch_op.drop_column("spend_cents")
        batch_op.drop_column("budget_cents")
        batch_op.drop_column("advertiser_user_id")
        batch_op.drop_column("is_self_serve")

