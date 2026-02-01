"""society calendar attendance rsvp

Revision ID: 3c9a0f4e2c12
Revises: 8d1c3a0c6b31
Create Date: 2026-02-01 11:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3c9a0f4e2c12'
down_revision = '8d1c3a0c6b31'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'society_calendar_attendance',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('responded_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['event_id'], ['society_calendar_event.id'], name='fk_soc_cal_att_event'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='fk_soc_cal_att_user'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_id', 'user_id', name='uq_society_calendar_attendance'),
    )
    with op.batch_alter_table('society_calendar_attendance', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_society_calendar_attendance_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_society_calendar_attendance_event_id'), ['event_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_society_calendar_attendance_user_id'), ['user_id'], unique=False)


def downgrade():
    with op.batch_alter_table('society_calendar_attendance', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_society_calendar_attendance_user_id'))
        batch_op.drop_index(batch_op.f('ix_society_calendar_attendance_event_id'))
        batch_op.drop_index(batch_op.f('ix_society_calendar_attendance_created_at'))
    op.drop_table('society_calendar_attendance')

