"""tournament personal bracket fields

Revision ID: 6a1b2c3d4e55
Revises: 4d0f2f45c8aa
Create Date: 2026-02-01 16:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6a1b2c3d4e55'
down_revision = '4d0f2f45c8aa'
branch_labels = None
depends_on = None


def upgrade():
    # tournament: allow personal tournaments (society_id nullable)
    with op.batch_alter_table('tournament', schema=None) as batch_op:
        batch_op.alter_column('society_id', existing_type=sa.Integer(), nullable=True)

    # tournament_team: add seed
    with op.batch_alter_table('tournament_team', schema=None) as batch_op:
        batch_op.add_column(sa.Column('seed', sa.Integer(), nullable=True))

    # tournament_match: bracket fields + nullable team slots
    with op.batch_alter_table('tournament_match', schema=None) as batch_op:
        batch_op.alter_column('home_team_id', existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column('away_team_id', existing_type=sa.Integer(), nullable=True)
        batch_op.add_column(sa.Column('winner_team_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('round_number', sa.Integer(), nullable=True, server_default='1'))
        batch_op.add_column(sa.Column('position', sa.Integer(), nullable=True, server_default='0'))
        batch_op.create_index(batch_op.f('ix_tournament_match_round_number'), ['round_number'], unique=False)
        batch_op.create_index(batch_op.f('ix_tournament_match_position'), ['position'], unique=False)
        batch_op.create_foreign_key('fk_tournament_match_winner_team', 'tournament_team', ['winner_team_id'], ['id'])


def downgrade():
    with op.batch_alter_table('tournament_match', schema=None) as batch_op:
        batch_op.drop_constraint('fk_tournament_match_winner_team', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_tournament_match_position'))
        batch_op.drop_index(batch_op.f('ix_tournament_match_round_number'))
        batch_op.drop_column('position')
        batch_op.drop_column('round_number')
        batch_op.drop_column('winner_team_id')
        batch_op.alter_column('away_team_id', existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column('home_team_id', existing_type=sa.Integer(), nullable=False)

    with op.batch_alter_table('tournament_team', schema=None) as batch_op:
        batch_op.drop_column('seed')

    with op.batch_alter_table('tournament', schema=None) as batch_op:
        batch_op.alter_column('society_id', existing_type=sa.Integer(), nullable=False)

