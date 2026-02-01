"""society role permissions

Revision ID: 5e2a7f2a9f1d
Revises: 0f3a5f01b2c1
Create Date: 2026-02-01 10:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5e2a7f2a9f1d'
down_revision = '0f3a5f01b2c1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'society_role_permission',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('society_id', sa.Integer(), nullable=False),
        sa.Column('role_name', sa.String(length=50), nullable=False),
        sa.Column('permission_id', sa.Integer(), nullable=False),
        sa.Column('effect', sa.String(length=10), nullable=False, server_default='allow'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['user.id'], name='fk_society_role_perm_created_by'),
        sa.ForeignKeyConstraint(['permission_id'], ['permission.id'], name='fk_society_role_perm_permission'),
        sa.ForeignKeyConstraint(['society_id'], ['society.id'], name='fk_society_role_perm_society'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('society_id', 'role_name', 'permission_id', name='uq_society_role_permission'),
    )
    with op.batch_alter_table('society_role_permission', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_society_role_permission_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_society_role_permission_permission_id'), ['permission_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_society_role_permission_role_name'), ['role_name'], unique=False)
        batch_op.create_index(batch_op.f('ix_society_role_permission_society_id'), ['society_id'], unique=False)


def downgrade():
    with op.batch_alter_table('society_role_permission', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_society_role_permission_society_id'))
        batch_op.drop_index(batch_op.f('ix_society_role_permission_role_name'))
        batch_op.drop_index(batch_op.f('ix_society_role_permission_permission_id'))
        batch_op.drop_index(batch_op.f('ix_society_role_permission_created_at'))
    op.drop_table('society_role_permission')

