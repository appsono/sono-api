"""Add audio files and user upload limits

Revision ID: 36a3570455fb
Revises: 654dffad2c96
Create Date: 2025-09-24 15:58:22.695017+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '36a3570455fb'
down_revision: Union[str, None] = '654dffad2c96'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add max_audio_uploads column to users table
    op.add_column('users', sa.Column('max_audio_uploads', sa.Integer(), nullable=True))
    op.execute("UPDATE users SET max_audio_uploads = 25 WHERE max_audio_uploads IS NULL")
    op.alter_column('users', 'max_audio_uploads', nullable=False)
    
    # Create audio_files table
    op.create_table('audio_files',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('original_filename', sa.String(), nullable=True),
        sa.Column('stored_filename', sa.String(), nullable=True),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=True),
        sa.Column('content_type', sa.String(), nullable=True),
        sa.Column('file_url', sa.String(), nullable=True),
        sa.Column('upload_date', sa.DateTime(), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=True),
        sa.Column('owner_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audio_files_id', 'audio_files', ['id'])
    op.create_index('ix_audio_files_original_filename', 'audio_files', ['original_filename'])
    op.create_index('ix_audio_files_stored_filename', 'audio_files', ['stored_filename'], unique=True)


def downgrade() -> None:
    pass
