"""Merge multiple heads

Revision ID: e6b09701f3d5
Revises: a8f3c2d1e9b5, b2e9f4a1c3d7
Create Date: 2026-06-25 15:20:08.545597

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6b09701f3d5'
down_revision: Union[str, Sequence[str], None] = ('a8f3c2d1e9b5', 'b2e9f4a1c3d7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
