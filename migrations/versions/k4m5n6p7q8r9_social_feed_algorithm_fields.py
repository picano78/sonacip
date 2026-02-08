"""social feed algorithm fields

Revision ID: k4m5n6p7q8r9
Revises: j2a4b6c8d0e1
Create Date: 2026-02-08 10:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "k4m5n6p7q8r9"
down_revision = "j2a4b6c8d0e1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("social_setting", schema=None) as batch_op:
        batch_op.add_column(sa.Column("priority_followed", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("priority_friends", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("priority_others", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("weight_engagement", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("weight_recency", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("weight_promoted", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("weight_official", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("weight_tournament", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("weight_automation", sa.Float(), nullable=True))


def downgrade():
    with op.batch_alter_table("social_setting", schema=None) as batch_op:
        batch_op.drop_column("weight_automation")
        batch_op.drop_column("weight_tournament")
        batch_op.drop_column("weight_official")
        batch_op.drop_column("weight_promoted")
        batch_op.drop_column("weight_recency")
        batch_op.drop_column("weight_engagement")
        batch_op.drop_column("priority_others")
        batch_op.drop_column("priority_friends")
        batch_op.drop_column("priority_followed")
