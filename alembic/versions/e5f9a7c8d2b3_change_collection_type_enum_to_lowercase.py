"""Change collection type enum to lowercase

Revision ID: e5f9a7c8d2b3
Revises: d4e8f9a5c3b2
Create Date: 2025-12-05 00:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f9a7c8d2b3'
down_revision: Union[str, None] = 'd4e8f9a5c3b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create new enum type with lowercase values
    op.execute("CREATE TYPE collectiontype_new AS ENUM ('album', 'playlist', 'compilation')")

    # Update existing data to lowercase (in case there's any)
    op.execute("""
        ALTER TABLE collections
        ALTER COLUMN collection_type TYPE collectiontype_new
        USING (lower(collection_type::text)::collectiontype_new)
    """)

    # Drop the old enum type
    op.execute("DROP TYPE collectiontype")

    # Rename the new enum type to the original name
    op.execute("ALTER TYPE collectiontype_new RENAME TO collectiontype")


def downgrade() -> None:
    # Create enum type with uppercase values
    op.execute("CREATE TYPE collectiontype_new AS ENUM ('ALBUM', 'PLAYLIST', 'COMPILATION')")

    # Update existing data back to uppercase
    op.execute("""
        ALTER TABLE collections
        ALTER COLUMN collection_type TYPE collectiontype_new
        USING (upper(collection_type::text)::collectiontype_new)
    """)

    # Drop the old enum type
    op.execute("DROP TYPE collectiontype")

    # Rename the new enum type to the original name
    op.execute("ALTER TYPE collectiontype_new RENAME TO collectiontype")
