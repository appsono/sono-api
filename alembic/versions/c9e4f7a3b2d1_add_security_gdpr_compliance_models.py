"""Add security and GDPR compliance models

Revision ID: c9e4f7a3b2d1
Revises: 46b0a24f02d8
Create Date: 2025-11-23 00:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9e4f7a3b2d1'
down_revision: Union[str, None] = '46b0a24f02d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create revoked_tokens table for token blacklist
    op.create_table('revoked_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('jti', sa.String(), nullable=False),
        sa.Column('token', sa.Text(), nullable=False),
        sa.Column('token_type', sa.String(length=20), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('reason', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_revoked_tokens_id'), 'revoked_tokens', ['id'], unique=False)
    op.create_index(op.f('ix_revoked_tokens_jti'), 'revoked_tokens', ['jti'], unique=True)

    # Create audit_logs table for persistent audit logging
    op.create_table('audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('resource_type', sa.String(), nullable=True),
        sa.Column('resource_id', sa.String(), nullable=True),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('user_agent', sa.String(), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)
    op.create_index(op.f('ix_audit_logs_timestamp'), 'audit_logs', ['timestamp'], unique=False)
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)

    # Create user_consents table for GDPR consent tracking
    op.create_table('user_consents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('consent_type', sa.String(), nullable=False),
        sa.Column('consent_version', sa.String(), nullable=False),
        sa.Column('given_at', sa.DateTime(), nullable=False),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('withdrawn_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'consent_type', 'consent_version', name='uq_user_consent')
    )
    op.create_index(op.f('ix_user_consents_id'), 'user_consents', ['id'], unique=False)

    # Create data_retention_policies table for retention policy management
    op.create_table('data_retention_policies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('data_type', sa.String(), nullable=False),
        sa.Column('retention_days', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('data_type')
    )
    op.create_index(op.f('ix_data_retention_policies_id'), 'data_retention_policies', ['id'], unique=False)

    # Create user_deletion_requests table for GDPR right to be forgotten
    op.create_table('user_deletion_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('requested_at', sa.DateTime(), nullable=False),
        sa.Column('scheduled_deletion_at', sa.DateTime(), nullable=False),
        sa.Column('deletion_type', sa.String(length=20), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_deletion_requests_id'), 'user_deletion_requests', ['id'], unique=False)


def downgrade() -> None:
    # Drop all created tables
    op.drop_index(op.f('ix_user_deletion_requests_id'), table_name='user_deletion_requests')
    op.drop_table('user_deletion_requests')

    op.drop_index(op.f('ix_data_retention_policies_id'), table_name='data_retention_policies')
    op.drop_table('data_retention_policies')

    op.drop_index(op.f('ix_user_consents_id'), table_name='user_consents')
    op.drop_table('user_consents')

    op.drop_index(op.f('ix_audit_logs_action'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_timestamp'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_id'), table_name='audit_logs')
    op.drop_table('audit_logs')

    op.drop_index(op.f('ix_revoked_tokens_jti'), table_name='revoked_tokens')
    op.drop_index(op.f('ix_revoked_tokens_id'), table_name='revoked_tokens')
    op.drop_table('revoked_tokens')
