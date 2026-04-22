"""society invites and audit scope

Revision ID: 0f3a5f01b2c1
Revises: 78b7221f7c74
Create Date: 2026-02-01 10:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0f3a5f01b2c1'
down_revision = '78b7221f7c74'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('audit_log', schema=None) as batch_op:
        batch_op.add_column(sa.Column('society_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_audit_log_society_id'), ['society_id'], unique=False)
        batch_op.create_foreign_key('fk_audit_log_society', 'society', ['society_id'], ['id'])

    op.create_table(
        'society_invite',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('society_id', sa.Integer(), nullable=False),
        sa.Column('invited_user_id', sa.Integer(), nullable=False),
        sa.Column('invited_by', sa.Integer(), nullable=False),
        sa.Column('requested_role', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('note', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('responded_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['invited_by'], ['user.id'], name='fk_society_invite_invited_by'),
        sa.ForeignKeyConstraint(['invited_user_id'], ['user.id'], name='fk_society_invite_invited_user'),
        sa.ForeignKeyConstraint(['society_id'], ['society.id'], name='fk_society_invite_society'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('society_id', 'invited_user_id', 'status', name='uq_society_invite_active'),
    )
    with op.batch_alter_table('society_invite', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_society_invite_society_id'), ['society_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_society_invite_invited_user_id'), ['invited_user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_society_invite_created_at'), ['created_at'], unique=False)


def downgrade():
    with op.batch_alter_table('society_invite', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_society_invite_created_at'))
        batch_op.drop_index(batch_op.f('ix_society_invite_invited_user_id'))
        batch_op.drop_index(batch_op.f('ix_society_invite_society_id'))
    op.drop_table('society_invite')

    with op.batch_alter_table('audit_log', schema=None) as batch_op:
        batch_op.drop_constraint('fk_audit_log_society', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_audit_log_society_id'))
        batch_op.drop_column('society_id')

