"""linkedin_profiles_career_education_skills_connections

Revision ID: 0a2a8dacd6c8
Revises: i7j8k9l0m1n2
Create Date: 2026-02-05 22:16:14.442110

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = '0a2a8dacd6c8'
down_revision = 'i7j8k9l0m1n2'
branch_labels = None
depends_on = None


def _table_exists(table_name):
    conn = op.get_bind()
    insp = inspect(conn)
    return table_name in insp.get_table_names()


def _column_exists(table_name, column_name):
    conn = op.get_bind()
    insp = inspect(conn)
    if table_name not in insp.get_table_names():
        return False
    columns = [c['name'] for c in insp.get_columns(table_name)]
    return column_name in columns


def upgrade():
    if not _column_exists('user', 'language'):
        op.add_column('user', sa.Column('language', sa.String(5), server_default='it'))

    if not _table_exists('career'):
        op.create_table('career',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(200), nullable=False),
            sa.Column('company', sa.String(200), nullable=False),
            sa.Column('company_logo', sa.String(255), nullable=True),
            sa.Column('location', sa.String(200), nullable=True),
            sa.Column('employment_type', sa.String(50), nullable=True),
            sa.Column('start_date', sa.Date(), nullable=False),
            sa.Column('end_date', sa.Date(), nullable=True),
            sa.Column('is_current', sa.Boolean(), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('skills', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.PrimaryKeyConstraint('id')
        )

    if not _table_exists('education'):
        op.create_table('education',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('school', sa.String(200), nullable=False),
            sa.Column('school_logo', sa.String(255), nullable=True),
            sa.Column('degree', sa.String(200), nullable=True),
            sa.Column('field_of_study', sa.String(200), nullable=True),
            sa.Column('start_year', sa.Integer(), nullable=True),
            sa.Column('end_year', sa.Integer(), nullable=True),
            sa.Column('grade', sa.String(50), nullable=True),
            sa.Column('activities', sa.Text(), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.PrimaryKeyConstraint('id')
        )

    if not _table_exists('skill'):
        op.create_table('skill',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(100), nullable=False),
            sa.Column('category', sa.String(50), nullable=True),
            sa.Column('endorsement_count', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.PrimaryKeyConstraint('id')
        )

    if not _table_exists('skill_endorsement'):
        op.create_table('skill_endorsement',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('skill_id', sa.Integer(), nullable=False),
            sa.Column('endorsed_by_id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['endorsed_by_id'], ['user.id']),
            sa.ForeignKeyConstraint(['skill_id'], ['skill.id']),
            sa.PrimaryKeyConstraint('id')
        )

    if not _table_exists('connection'):
        op.create_table('connection',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('requester_id', sa.Integer(), nullable=False),
            sa.Column('addressee_id', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(20), nullable=True),
            sa.Column('message', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['addressee_id'], ['user.id']),
            sa.ForeignKeyConstraint(['requester_id'], ['user.id']),
            sa.PrimaryKeyConstraint('id')
        )

    if not _table_exists('profile_section'):
        op.create_table('profile_section',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(100), nullable=False),
            sa.Column('section_type', sa.String(50), nullable=True),
            sa.Column('icon', sa.String(50), nullable=True),
            sa.Column('is_enabled', sa.Boolean(), nullable=True),
            sa.Column('display_order', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )


def downgrade():
    for table in ['profile_section', 'connection', 'skill_endorsement', 'skill', 'education', 'career']:
        if _table_exists(table):
            op.drop_table(table)

    if _column_exists('user', 'language'):
        op.drop_column('user', 'language')
