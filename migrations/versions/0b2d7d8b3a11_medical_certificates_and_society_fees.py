"""medical certificates and society fees

Revision ID: 0b2d7d8b3a11
Revises: 2a1f84a6c3f1
Create Date: 2026-02-01 13:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0b2d7d8b3a11'
down_revision = '2a1f84a6c3f1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'medical_certificate',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('society_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('issued_on', sa.Date(), nullable=True),
        sa.Column('expires_on', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['user.id'], name='fk_medical_certificate_created_by'),
        sa.ForeignKeyConstraint(['society_id'], ['society.id'], name='fk_medical_certificate_society'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='fk_medical_certificate_user'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('society_id', 'user_id', 'expires_on', name='uq_medical_certificate_society_user_expires'),
    )
    with op.batch_alter_table('medical_certificate', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_medical_certificate_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_medical_certificate_expires_on'), ['expires_on'], unique=False)
        batch_op.create_index(batch_op.f('ix_medical_certificate_society_id'), ['society_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_medical_certificate_user_id'), ['user_id'], unique=False)

    op.create_table(
        'society_fee',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('society_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('amount_cents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('currency', sa.String(length=3), nullable=True, server_default='EUR'),
        sa.Column('due_on', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['user.id'], name='fk_society_fee_created_by'),
        sa.ForeignKeyConstraint(['society_id'], ['society.id'], name='fk_society_fee_society'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='fk_society_fee_user'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('society_fee', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_society_fee_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_society_fee_due_on'), ['due_on'], unique=False)
        batch_op.create_index(batch_op.f('ix_society_fee_society_id'), ['society_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_society_fee_user_id'), ['user_id'], unique=False)

    op.create_table(
        'medical_certificate_reminder_sent',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('certificate_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=50), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['certificate_id'], ['medical_certificate.id'], name='fk_med_cert_rem_cert'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='fk_med_cert_rem_user'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('certificate_id', 'user_id', 'kind', name='uq_medical_certificate_reminder_sent'),
    )
    with op.batch_alter_table('medical_certificate_reminder_sent', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_medical_certificate_reminder_sent_certificate_id'), ['certificate_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_medical_certificate_reminder_sent_sent_at'), ['sent_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_medical_certificate_reminder_sent_user_id'), ['user_id'], unique=False)

    op.create_table(
        'society_fee_reminder_sent',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('fee_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=50), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['fee_id'], ['society_fee.id'], name='fk_soc_fee_rem_fee'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='fk_soc_fee_rem_user'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('fee_id', 'user_id', 'kind', name='uq_society_fee_reminder_sent'),
    )
    with op.batch_alter_table('society_fee_reminder_sent', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_society_fee_reminder_sent_fee_id'), ['fee_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_society_fee_reminder_sent_sent_at'), ['sent_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_society_fee_reminder_sent_user_id'), ['user_id'], unique=False)


def downgrade():
    with op.batch_alter_table('society_fee_reminder_sent', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_society_fee_reminder_sent_user_id'))
        batch_op.drop_index(batch_op.f('ix_society_fee_reminder_sent_sent_at'))
        batch_op.drop_index(batch_op.f('ix_society_fee_reminder_sent_fee_id'))
    op.drop_table('society_fee_reminder_sent')

    with op.batch_alter_table('medical_certificate_reminder_sent', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_medical_certificate_reminder_sent_user_id'))
        batch_op.drop_index(batch_op.f('ix_medical_certificate_reminder_sent_sent_at'))
        batch_op.drop_index(batch_op.f('ix_medical_certificate_reminder_sent_certificate_id'))
    op.drop_table('medical_certificate_reminder_sent')

    with op.batch_alter_table('society_fee', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_society_fee_user_id'))
        batch_op.drop_index(batch_op.f('ix_society_fee_society_id'))
        batch_op.drop_index(batch_op.f('ix_society_fee_due_on'))
        batch_op.drop_index(batch_op.f('ix_society_fee_created_at'))
    op.drop_table('society_fee')

    with op.batch_alter_table('medical_certificate', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_medical_certificate_user_id'))
        batch_op.drop_index(batch_op.f('ix_medical_certificate_society_id'))
        batch_op.drop_index(batch_op.f('ix_medical_certificate_expires_on'))
        batch_op.drop_index(batch_op.f('ix_medical_certificate_created_at'))
    op.drop_table('medical_certificate')

