"""ads autopilot campaigns and creatives

Revision ID: 9f0c2b1a7d10
Revises: 7f2e9c1d0a12
Create Date: 2026-02-01 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9f0c2b1a7d10"
down_revision = "7f2e9c1d0a12"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ad_campaign",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("objective", sa.String(length=50), nullable=True),
        sa.Column("society_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("starts_at", sa.DateTime(), nullable=True),
        sa.Column("ends_at", sa.DateTime(), nullable=True),
        sa.Column("max_impressions", sa.Integer(), nullable=True),
        sa.Column("max_clicks", sa.Integer(), nullable=True),
        sa.Column("autopilot", sa.Boolean(), nullable=True),
        sa.Column("impressions_count", sa.Integer(), nullable=True),
        sa.Column("clicks_count", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], name="fk_ad_campaign_created_by"),
        sa.ForeignKeyConstraint(["society_id"], ["society.id"], name="fk_ad_campaign_society"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("ad_campaign", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_ad_campaign_created_at"), ["created_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_ad_campaign_is_active"), ["is_active"], unique=False)
        batch_op.create_index(batch_op.f("ix_ad_campaign_society_id"), ["society_id"], unique=False)

    op.create_table(
        "ad_creative",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("placement", sa.String(length=50), nullable=False),
        sa.Column("headline", sa.String(length=120), nullable=True),
        sa.Column("body", sa.String(length=500), nullable=True),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("link_url", sa.String(length=800), nullable=False),
        sa.Column("cta_label", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("weight", sa.Integer(), nullable=True),
        sa.Column("impressions_count", sa.Integer(), nullable=True),
        sa.Column("clicks_count", sa.Integer(), nullable=True),
        sa.Column("last_served_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["ad_campaign.id"], name="fk_ad_creative_campaign"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], name="fk_ad_creative_created_by"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("ad_creative", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_ad_creative_campaign_id"), ["campaign_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_ad_creative_created_at"), ["created_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_ad_creative_is_active"), ["is_active"], unique=False)
        batch_op.create_index(batch_op.f("ix_ad_creative_placement"), ["placement"], unique=False)

    op.create_table(
        "ad_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("creative_id", sa.Integer(), nullable=False),
        sa.Column("placement", sa.String(length=50), nullable=False),
        sa.Column("society_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("ip", sa.String(length=80), nullable=True),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["ad_campaign.id"], name="fk_ad_event_campaign"),
        sa.ForeignKeyConstraint(["creative_id"], ["ad_creative.id"], name="fk_ad_event_creative"),
        sa.ForeignKeyConstraint(["society_id"], ["society.id"], name="fk_ad_event_society"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], name="fk_ad_event_user"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("ad_event", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_ad_event_campaign_id"), ["campaign_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_ad_event_created_at"), ["created_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_ad_event_creative_id"), ["creative_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_ad_event_kind"), ["kind"], unique=False)
        batch_op.create_index(batch_op.f("ix_ad_event_placement"), ["placement"], unique=False)
        batch_op.create_index(batch_op.f("ix_ad_event_society_id"), ["society_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_ad_event_user_id"), ["user_id"], unique=False)


def downgrade():
    with op.batch_alter_table("ad_event", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ad_event_user_id"))
        batch_op.drop_index(batch_op.f("ix_ad_event_society_id"))
        batch_op.drop_index(batch_op.f("ix_ad_event_placement"))
        batch_op.drop_index(batch_op.f("ix_ad_event_kind"))
        batch_op.drop_index(batch_op.f("ix_ad_event_creative_id"))
        batch_op.drop_index(batch_op.f("ix_ad_event_created_at"))
        batch_op.drop_index(batch_op.f("ix_ad_event_campaign_id"))
    op.drop_table("ad_event")

    with op.batch_alter_table("ad_creative", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ad_creative_placement"))
        batch_op.drop_index(batch_op.f("ix_ad_creative_is_active"))
        batch_op.drop_index(batch_op.f("ix_ad_creative_created_at"))
        batch_op.drop_index(batch_op.f("ix_ad_creative_campaign_id"))
    op.drop_table("ad_creative")

    with op.batch_alter_table("ad_campaign", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ad_campaign_society_id"))
        batch_op.drop_index(batch_op.f("ix_ad_campaign_is_active"))
        batch_op.drop_index(batch_op.f("ix_ad_campaign_created_at"))
    op.drop_table("ad_campaign")

