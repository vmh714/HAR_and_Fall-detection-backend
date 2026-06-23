"""Add firmware_releases table

Revision ID: b2e9f4a1c3d7
Revises: 87ece1774913
Create Date: 2026-06-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2e9f4a1c3d7'
down_revision: Union[str, Sequence[str], None] = '1234567890ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'firmware_releases',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('version', sa.String(20), nullable=False),
        sa.Column('release_date', sa.Date(), nullable=False),
        sa.Column('changelog', sa.Text(), nullable=False),
        sa.Column('is_stable', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_latest', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('bin_filename', sa.String(200), nullable=False),
        sa.Column('bin_size', sa.Integer(), nullable=False),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('version'),
    )


def downgrade() -> None:
    op.drop_table('firmware_releases')
