"""coupons and redemptions

Revision ID: 4d0f2f45c8aa
Revises: 0b2d7d8b3a11
Create Date: 2026-02-01 13:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4d0f2f45c8aa'
down_revision = '0b2d7d8b3a11'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'coupon',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('discount_type', sa.String(length=20), nullable=True),
        sa.Column('discount_value', sa.Integer(), nullable=True),
        sa.Column('currency', sa.String(length=3), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('max_redemptions', sa.Integer(), nullable=True),
        sa.Column('redeemed_count', sa.Integer(), nullable=True),
        sa.Column('valid_from', sa.DateTime(), nullable=True),
        sa.Column('valid_until', sa.DateTime(), nullable=True),
        sa.Column('plan_id', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['user.id'], name='fk_coupon_created_by'),
        sa.ForeignKeyConstraint(['plan_id'], ['plan.id'], name='fk_coupon_plan'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    with op.batch_alter_table('coupon', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_coupon_code'), ['code'], unique=False)
        batch_op.create_index(batch_op.f('ix_coupon_created_at'), ['created_at'], unique=False)

    op.create_table(
        'coupon_redemption',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('coupon_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('society_id', sa.Integer(), nullable=True),
        sa.Column('subscription_id', sa.Integer(), nullable=True),
        sa.Column('payment_id', sa.Integer(), nullable=True),
        sa.Column('redeemed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['coupon_id'], ['coupon.id'], name='fk_coupon_redemption_coupon'),
        sa.ForeignKeyConstraint(['payment_id'], ['payment.id'], name='fk_coupon_redemption_payment'),
        sa.ForeignKeyConstraint(['society_id'], ['society.id'], name='fk_coupon_redemption_society'),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscription.id'], name='fk_coupon_redemption_subscription'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='fk_coupon_redemption_user'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('coupon_redemption', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_coupon_redemption_coupon_id'), ['coupon_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_coupon_redemption_redeemed_at'), ['redeemed_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_coupon_redemption_society_id'), ['society_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_coupon_redemption_user_id'), ['user_id'], unique=False)


def downgrade():
    with op.batch_alter_table('coupon_redemption', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_coupon_redemption_user_id'))
        batch_op.drop_index(batch_op.f('ix_coupon_redemption_society_id'))
        batch_op.drop_index(batch_op.f('ix_coupon_redemption_redeemed_at'))
        batch_op.drop_index(batch_op.f('ix_coupon_redemption_coupon_id'))
    op.drop_table('coupon_redemption')

    with op.batch_alter_table('coupon', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_coupon_created_at'))
        batch_op.drop_index(batch_op.f('ix_coupon_code'))
    op.drop_table('coupon')

