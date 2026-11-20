"""create_system_audit_logs_table

Revision ID: a0fe6dbc15fb
Revises: e450d9eb0b69
Create Date: 2026-11-20 06:46:29.328394+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a0fe6dbc15fb'
down_revision: Union[str, None] = 'e450d9eb0b69'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create monotonic sequence for audit records
    op.execute("CREATE SEQUENCE IF NOT EXISTS audit_sequence_num START WITH 1 INCREMENT BY 1;")

    op.create_table(
        'system_audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('sequence_number', sa.BigInteger(), server_default=sa.text("nextval('audit_sequence_num')"), nullable=False),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('actor_email', sa.String(length=255), nullable=True),
        sa.Column('actor_role', sa.String(length=100), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('resource_id', sa.String(length=100), nullable=False),
        sa.Column('state_before', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('state_after', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('diff_summary', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('ip_address', sa.String(length=50), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('correlation_id', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column('prev_record_hash', sa.String(length=64), nullable=False),
        sa.Column('record_hash', sa.String(length=64), nullable=False),
        sa.UniqueConstraint('sequence_number', name='uq_system_audit_logs_sequence'),
        sa.UniqueConstraint('record_hash', name='uq_system_audit_logs_record_hash'),
    )

    op.create_index('ix_system_audit_logs_sequence_number', 'system_audit_logs', ['sequence_number'])
    op.create_index('ix_system_audit_logs_actor_id', 'system_audit_logs', ['actor_id'])
    op.create_index('ix_system_audit_logs_actor_email', 'system_audit_logs', ['actor_email'])
    op.create_index('ix_system_audit_logs_action', 'system_audit_logs', ['action'])
    op.create_index('ix_system_audit_logs_resource_type', 'system_audit_logs', ['resource_type'])
    op.create_index('ix_system_audit_logs_resource_id', 'system_audit_logs', ['resource_id'])
    op.create_index('ix_system_audit_logs_correlation_id', 'system_audit_logs', ['correlation_id'])
    op.create_index('ix_system_audit_logs_created_at', 'system_audit_logs', ['created_at'])
    op.create_index('ix_system_audit_logs_record_hash', 'system_audit_logs', ['record_hash'])
    op.create_index('ix_audit_action_resource', 'system_audit_logs', ['action', 'resource_type'])
    op.create_index('ix_audit_created_actor', 'system_audit_logs', ['created_at', 'actor_id'])


def downgrade() -> None:
    op.drop_index('ix_audit_created_actor', table_name='system_audit_logs')
    op.drop_index('ix_audit_action_resource', table_name='system_audit_logs')
    op.drop_index('ix_system_audit_logs_record_hash', table_name='system_audit_logs')
    op.drop_index('ix_system_audit_logs_created_at', table_name='system_audit_logs')
    op.drop_index('ix_system_audit_logs_correlation_id', table_name='system_audit_logs')
    op.drop_index('ix_system_audit_logs_resource_id', table_name='system_audit_logs')
    op.drop_index('ix_system_audit_logs_resource_type', table_name='system_audit_logs')
    op.drop_index('ix_system_audit_logs_action', table_name='system_audit_logs')
    op.drop_index('ix_system_audit_logs_actor_email', table_name='system_audit_logs')
    op.drop_index('ix_system_audit_logs_actor_id', table_name='system_audit_logs')
    op.drop_index('ix_system_audit_logs_sequence_number', table_name='system_audit_logs')
    op.drop_table('system_audit_logs')
    op.execute("DROP SEQUENCE IF EXISTS audit_sequence_num;")
