"""add file url to chat message

Revision ID: xxxx
Revises: previous_revision
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('chat_message', sa.Column('file_url', sa.String(200), nullable=True))

def downgrade():
    op.drop_column('chat_message', 'file_url') 