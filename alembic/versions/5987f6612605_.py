"""create_initial_tables (or your original message for this revision)

Revision ID: 5987f6612605
Revises: 
Create Date: 2025-05-29 21:04:39.045437+02:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5987f6612605'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands to create users table ###
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=32), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('display_name', sa.String(length=32), nullable=True), # You had String(32) for display_name in your last models.py
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        # sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False), # Add if you have is_active in models
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_display_name'), 'users', ['display_name'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands to drop users table ###
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_display_name'), table_name='users')
    op.drop_table('users')
    # ### end Alembic commands ###
