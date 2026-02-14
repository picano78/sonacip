"""Add invoice_settings table

Revision ID: e1f2a3b4c5d6
Revises: 
Create Date: 2026-02-14 18:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e1f2a3b4c5d6'
down_revision = None  # Will be set to latest migration ID
branch_labels = None
depends_on = None


def upgrade():
    # Create invoice_settings table
    op.create_table('invoice_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(length=200), nullable=True),
        sa.Column('company_address', sa.Text(), nullable=True),
        sa.Column('company_city', sa.String(length=100), nullable=True),
        sa.Column('company_postal_code', sa.String(length=20), nullable=True),
        sa.Column('company_country', sa.String(length=100), nullable=True),
        sa.Column('company_vat', sa.String(length=50), nullable=True),
        sa.Column('company_tax_code', sa.String(length=50), nullable=True),
        sa.Column('company_phone', sa.String(length=50), nullable=True),
        sa.Column('company_email', sa.String(length=120), nullable=True),
        sa.Column('company_website', sa.String(length=200), nullable=True),
        sa.Column('invoice_prefix', sa.String(length=20), nullable=True),
        sa.Column('invoice_footer', sa.Text(), nullable=True),
        sa.Column('invoice_notes', sa.Text(), nullable=True),
        sa.Column('default_tax_rate', sa.Float(), nullable=True),
        sa.Column('logo_path', sa.String(length=500), nullable=True),
        sa.Column('enable_electronic_invoice', sa.Boolean(), nullable=True),
        sa.Column('e_invoice_provider', sa.String(length=50), nullable=True),
        sa.Column('e_invoice_api_key', sa.String(length=500), nullable=True),
        sa.Column('e_invoice_api_secret', sa.String(length=500), nullable=True),
        sa.Column('e_invoice_company_id', sa.String(length=100), nullable=True),
        sa.Column('sdi_code', sa.String(length=7), nullable=True),
        sa.Column('pec_email', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['updated_by'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('invoice_settings')
