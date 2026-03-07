"""Add token_invalidated_at to users table for session revocation

Revision ID: g2a3b4c5d6e7
Revises: f1a2b3c4d5e6
Create Date: 2026-03-07 12:48:00.267675+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g2a3b4c5d6e7'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add token_invalidated_at column to users table
    # When set, all tokens issued before this timestamp are rejected
    op.add_column('users', sa.Column('token_invalidated_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'token_invalidated_at')
