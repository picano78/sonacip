"""feed and notification indexes

Revision ID: 2d6c1a4b9f20
Revises: 1c7b9d2e0f91
Create Date: 2026-02-01 18:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2d6c1a4b9f20"
down_revision = "1c7b9d2e0f91"
branch_labels = None
depends_on = None


def upgrade():
    # Feed: scope filters
    with op.batch_alter_table("post", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_post_audience"), ["audience"], unique=False)
        batch_op.create_index(batch_op.f("ix_post_society_id"), ["society_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_post_target_user_id"), ["target_user_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_post_post_type"), ["post_type"], unique=False)

    # Notifications: fast unread counts + listing per user
    with op.batch_alter_table("notification", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_notification_user_id"), ["user_id"], unique=False)
        batch_op.create_index("ix_notification_user_unread", ["user_id", "is_read"], unique=False)

    # Tournaments: common filters
    with op.batch_alter_table("tournament_match", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_tournament_match_tournament_id"), ["tournament_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_tournament_match_match_date"), ["match_date"], unique=False)
        batch_op.create_index(batch_op.f("ix_tournament_match_status"), ["status"], unique=False)


def downgrade():
    with op.batch_alter_table("tournament_match", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_tournament_match_status"))
        batch_op.drop_index(batch_op.f("ix_tournament_match_match_date"))
        batch_op.drop_index(batch_op.f("ix_tournament_match_tournament_id"))

    with op.batch_alter_table("notification", schema=None) as batch_op:
        batch_op.drop_index("ix_notification_user_unread")
        batch_op.drop_index(batch_op.f("ix_notification_user_id"))

    with op.batch_alter_table("post", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_post_post_type"))
        batch_op.drop_index(batch_op.f("ix_post_target_user_id"))
        batch_op.drop_index(batch_op.f("ix_post_society_id"))
        batch_op.drop_index(batch_op.f("ix_post_audience"))

