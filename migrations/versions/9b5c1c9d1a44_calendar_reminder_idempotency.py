"""calendar reminder idempotency

Revision ID: 9b5c1c9d1a44
Revises: 3c9a0f4e2c12
Create Date: 2026-02-01 12:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9b5c1c9d1a44'
down_revision = '3c9a0f4e2c12'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'society_calendar_reminder_sent',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=50), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['event_id'], ['society_calendar_event.id'], name='fk_soc_cal_rem_event'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='fk_soc_cal_rem_user'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_id', 'user_id', 'kind', name='uq_society_calendar_reminder_sent'),
    )
    with op.batch_alter_table('society_calendar_reminder_sent', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_society_calendar_reminder_sent_event_id'), ['event_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_society_calendar_reminder_sent_sent_at'), ['sent_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_society_calendar_reminder_sent_user_id'), ['user_id'], unique=False)


def downgrade():
    with op.batch_alter_table('society_calendar_reminder_sent', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_society_calendar_reminder_sent_user_id'))
        batch_op.drop_index(batch_op.f('ix_society_calendar_reminder_sent_sent_at'))
        batch_op.drop_index(batch_op.f('ix_society_calendar_reminder_sent_event_id'))
    op.drop_table('society_calendar_reminder_sent')

