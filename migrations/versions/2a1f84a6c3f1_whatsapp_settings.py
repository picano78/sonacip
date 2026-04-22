"""whatsapp settings

Revision ID: 2a1f84a6c3f1
Revises: 9b5c1c9d1a44
Create Date: 2026-02-01 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2a1f84a6c3f1'
down_revision = '9b5c1c9d1a44'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'whatsapp_setting',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.Column('provider', sa.String(length=50), nullable=True),
        sa.Column('api_url', sa.String(length=500), nullable=True),
        sa.Column('api_token', sa.String(length=500), nullable=True),
        sa.Column('from_number', sa.String(length=50), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['updated_by'], ['user.id'], name='fk_whatsapp_setting_updated_by'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('whatsapp_setting')

