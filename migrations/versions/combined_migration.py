"""Combined migration

Revision ID: combined_migration
Revises: 
Create Date: 2024-01-20
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'combined_migration'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Create Category table
    op.create_table('category',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('description', sa.String(200), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # Create QuestionSet table
    op.create_table('questionset',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(20), nullable=True),
        sa.Column('time_limit', sa.Integer(), nullable=False, server_default='300'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )

    # Create User table
    op.create_table('user',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('password', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('is_admin', sa.Boolean(), default=False),
        sa.Column('question_set', sa.Integer(), sa.ForeignKey('questionset.id')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # Create Question table with new columns
    op.create_table('question',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('question_type', sa.String(20), nullable=False, server_default='multiple_choice'),
        sa.Column('image_url', sa.String(200), nullable=True),
        sa.Column('option1', sa.String(), nullable=True),
        sa.Column('option2', sa.String(), nullable=True),
        sa.Column('option3', sa.String(), nullable=True),
        sa.Column('option4', sa.String(), nullable=True),
        sa.Column('correct_option', sa.CHAR(), nullable=False),
        sa.Column('verified', sa.Boolean(), nullable=False, default=False),
        sa.Column('creator_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('question_set_id', sa.Integer(), sa.ForeignKey('questionset.id')),
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('category.id')),
        sa.Column('difficulty', sa.String(20), server_default='medium'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create Result table
    op.create_table('result',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('total_number', sa.Integer(), nullable=False),
        sa.Column('correct', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('not_attempt', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('incorrect', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('time_taken', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('question_set_id', sa.Integer(), sa.ForeignKey('questionset.id')),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('result')
    op.drop_table('question')
    op.drop_table('user')
    op.drop_table('questionset')
    op.drop_table('category') 