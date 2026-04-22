"""user_email_confirmation_fields

Revision ID: c9d1e2f3a4b5
Revises: k4m5n6p7q8r9
Create Date: 2026-02-09 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "c9d1e2f3a4b5"
down_revision = "k4m5n6p7q8r9"
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


def _index_exists(table_name: str, index_name: str) -> bool:
    conn = op.get_bind()
    insp = inspect(conn)
    if table_name not in insp.get_table_names():
        return False
    return any(idx["name"] == index_name for idx in insp.get_indexes(table_name))


def upgrade():
    table_name = "user"
    if not _table_exists(table_name):
        return

    with op.batch_alter_table(table_name, schema=None) as batch_op:
        if not _column_exists(table_name, "email_confirmed"):
            batch_op.add_column(sa.Column("email_confirmed", sa.Boolean(), nullable=True))
        if not _column_exists(table_name, "email_confirm_token"):
            batch_op.add_column(sa.Column("email_confirm_token", sa.String(length=128), nullable=True))
        if not _column_exists(table_name, "email_confirm_sent_at"):
            batch_op.add_column(sa.Column("email_confirm_sent_at", sa.DateTime(), nullable=True))

    if _column_exists(table_name, "email_confirmed"):
        user_table = sa.table(
            table_name,
            sa.column("email_confirmed", sa.Boolean()),
        )
        op.execute(
            user_table.update()
            .where(user_table.c.email_confirmed.is_(None))
            .values(email_confirmed=sa.false())
        )

    idx_name = op.f("ix_user_email_confirm_token")
    if _column_exists(table_name, "email_confirm_token") and not _index_exists(table_name, idx_name):
        op.create_index(idx_name, table_name, ["email_confirm_token"], unique=False)


def downgrade():
    table_name = "user"
    if not _table_exists(table_name):
        return

    idx_name = op.f("ix_user_email_confirm_token")
    if _index_exists(table_name, idx_name):
        op.drop_index(idx_name, table_name=table_name)

    with op.batch_alter_table(table_name, schema=None) as batch_op:
        if _column_exists(table_name, "email_confirm_sent_at"):
            batch_op.drop_column("email_confirm_sent_at")
        if _column_exists(table_name, "email_confirm_token"):
            batch_op.drop_column("email_confirm_token")
        if _column_exists(table_name, "email_confirmed"):
            batch_op.drop_column("email_confirmed")
