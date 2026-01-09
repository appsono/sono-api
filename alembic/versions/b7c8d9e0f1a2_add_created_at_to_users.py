"""Add created_at timestamp to users table

Revision ID: b7c8d9e0f1a2
Revises: e5f9a7c8d2b3
Create Date: 2025-12-25 00:00:00.000000+00:00

"""
from typing import Sequence, Union
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, None] = 'e5f9a7c8d2b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add created_at column to users table
    # For existing users, set the default to the current timestamp (migration time)
    op.add_column('users', sa.Column('created_at', sa.DateTime(), nullable=True))

    # Update existing rows to have the migration timestamp as their created_at
    op.execute(f"UPDATE users SET created_at = '{datetime.utcnow().isoformat()}' WHERE created_at IS NULL")

    # Now make the column non-nullable
    op.alter_column('users', 'created_at', nullable=False)


def downgrade() -> None:
    op.drop_column('users', 'created_at')
