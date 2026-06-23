"""Add verification_sessions table

Revision ID: a8f3c2d1e9b5
Revises: cade8bab7f74
Create Date: 2026-06-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'a8f3c2d1e9b5'
down_revision: Union[str, Sequence[str], None] = 'cade8bab7f74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'verification_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('device_id', sa.String(100), nullable=False),
        sa.Column('wearer_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('subject_code', sa.String(4), nullable=False),
        sa.Column('activity_code', sa.String(3), nullable=False),
        sa.Column('trial_no', sa.String(3), nullable=False),
        sa.Column('sample_count', sa.Integer(), nullable=True),
        sa.Column('duration_s', sa.Float(), nullable=True),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['device_id'], ['devices.device_id']),
        sa.ForeignKeyConstraint(['wearer_id'], ['wearers.id']),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_verification_sessions_org_id', 'verification_sessions', ['org_id'])
    op.create_index('ix_verification_sessions_device_id', 'verification_sessions', ['device_id'])


def downgrade() -> None:
    op.drop_index('ix_verification_sessions_device_id', table_name='verification_sessions')
    op.drop_index('ix_verification_sessions_org_id', table_name='verification_sessions')
    op.drop_table('verification_sessions')
