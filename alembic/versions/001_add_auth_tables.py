"""Add authentication tables (organizations, api_keys, webhooks)

Revision ID: 001_add_auth_tables
Revises:
Create Date: 2024-01-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_add_auth_tables'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Organizations table
    op.create_table(
        'organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('slug', sa.String(50), unique=True, nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('settings', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    # API Keys table
    op.create_table(
        'api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('key_hash', sa.String(64), unique=True, nullable=False),
        sa.Column('key_prefix', sa.String(8), nullable=False),
        sa.Column('scopes', postgresql.JSONB(), default=['read']),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('rate_limit', sa.Integer(), default=1000),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    # API Key Usage table
    op.create_table(
        'api_key_usage',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('api_key_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('api_keys.id', ondelete='CASCADE'), nullable=False),
        sa.Column('endpoint', sa.String(200), nullable=False),
        sa.Column('method', sa.String(10), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=False),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, index=True),
    )

    # Webhooks table
    op.create_table(
        'webhooks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('secret', sa.String(64), nullable=False),
        sa.Column('events', postgresql.JSONB(), default=['document.processed']),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('retry_count', sa.Integer(), default=3),
        sa.Column('timeout_seconds', sa.Integer(), default=30),
        sa.Column('headers', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    # Webhook Deliveries table
    op.create_table(
        'webhook_deliveries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('webhook_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('webhooks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column('response_status', sa.Integer(), nullable=True),
        sa.Column('response_body', sa.Text(), nullable=True),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column('attempt_count', sa.Integer(), default=1),
        sa.Column('success', sa.Boolean(), default=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    # Add extraction_method column to extractions table
    op.add_column(
        'extractions',
        sa.Column('extraction_method', sa.String(20), nullable=False, server_default='regex')
    )

    # Add organization_id column to documents table for multi-tenancy
    op.add_column(
        'documents',
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_index('ix_documents_organization_id', 'documents', ['organization_id'])


def downgrade() -> None:
    op.drop_index('ix_documents_organization_id', 'documents')
    op.drop_column('documents', 'organization_id')
    op.drop_column('extractions', 'extraction_method')
    op.drop_table('webhook_deliveries')
    op.drop_table('webhooks')
    op.drop_table('api_key_usage')
    op.drop_table('api_keys')
    op.drop_table('organizations')
