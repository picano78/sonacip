"""add_app_icon_url_to_appearance_setting

Revision ID: d2f4a6c8e0b1
Revises: fcec1bf08c43, c9d1e2f3a4b5
Create Date: 2026-02-10

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "d2f4a6c8e0b1"
down_revision = ("fcec1bf08c43", "c9d1e2f3a4b5")
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    insp = inspect(conn)
    return table_name in insp.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    conn = op.get_bind()
    insp = inspect(conn)
    if table_name not in insp.get_table_names():
        return False
    columns = [c["name"] for c in insp.get_columns(table_name)]
    return column_name in columns


def upgrade():
    table_name = "appearance_setting"
    if not _table_exists(table_name):
        return

    with op.batch_alter_table(table_name, schema=None) as batch_op:
        if not _column_exists(table_name, "app_icon_url"):
            batch_op.add_column(sa.Column("app_icon_url", sa.String(length=255), nullable=True))


def downgrade():
    table_name = "appearance_setting"
    if not _table_exists(table_name):
        return

    with op.batch_alter_table(table_name, schema=None) as batch_op:
        if _column_exists(table_name, "app_icon_url"):
            batch_op.drop_column("app_icon_url")

