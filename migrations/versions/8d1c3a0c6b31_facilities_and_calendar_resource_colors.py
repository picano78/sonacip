"""facilities and calendar resource colors

Revision ID: 8d1c3a0c6b31
Revises: 5e2a7f2a9f1d
Create Date: 2026-02-01 11:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8d1c3a0c6b31'
down_revision = '5e2a7f2a9f1d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'facility',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('society_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('address', sa.String(length=255), nullable=True),
        sa.Column('capacity', sa.Integer(), nullable=True),
        sa.Column('color', sa.String(length=20), nullable=True, server_default='#0d6efd'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['user.id'], name='fk_facility_created_by'),
        sa.ForeignKeyConstraint(['society_id'], ['society.id'], name='fk_facility_society'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('facility', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_facility_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_facility_society_id'), ['society_id'], unique=False)

    with op.batch_alter_table('society_calendar_event', schema=None) as batch_op:
        batch_op.add_column(sa.Column('facility_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('color', sa.String(length=20), nullable=True, server_default='#212529'))
        batch_op.create_index(batch_op.f('ix_society_calendar_event_facility_id'), ['facility_id'], unique=False)
        batch_op.create_foreign_key('fk_society_calendar_event_facility', 'facility', ['facility_id'], ['id'])


def downgrade():
    with op.batch_alter_table('society_calendar_event', schema=None) as batch_op:
        batch_op.drop_constraint('fk_society_calendar_event_facility', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_society_calendar_event_facility_id'))
        batch_op.drop_column('color')
        batch_op.drop_column('facility_id')

    with op.batch_alter_table('facility', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_facility_society_id'))
        batch_op.drop_index(batch_op.f('ix_facility_created_at'))
    op.drop_table('facility')

