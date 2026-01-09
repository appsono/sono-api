"""Add audio files and user upload limits

Revision ID: 654dffad2c96
Revises: 60a7d5e96bc2
Create Date: 2025-09-24 15:58:20.471993+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '654dffad2c96'
down_revision: Union[str, None] = '60a7d5e96bc2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
