"""Add fall_threshold to devices

Revision ID: a7b3f9c1d2e4
Revises: cade8bab7f74
Create Date: 2026-06-18 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b3f9c1d2e4'
down_revision: Union[str, Sequence[str], None] = 'cade8bab7f74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('devices', sa.Column('fall_threshold', sa.Float(), nullable=False, server_default='0.6'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('devices', 'fall_threshold')
