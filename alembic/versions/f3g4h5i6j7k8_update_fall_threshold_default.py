"""update fall_threshold default

Revision ID: f3g4h5i6j7k8
Revises: e2f3a4b5c6d7
Create Date: 2026-06-29 11:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3g4h5i6j7k8'
down_revision: Union[str, Sequence[str], None] = 'e2f3a4b5c6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update server default
    op.alter_column('devices', 'fall_threshold', server_default='0.25')
    # Update existing values that were using the old default
    op.execute("UPDATE devices SET fall_threshold = 0.25 WHERE fall_threshold = 0.6")


def downgrade() -> None:
    # Revert server default
    op.alter_column('devices', 'fall_threshold', server_default='0.6')
    # Revert updated values back
    op.execute("UPDATE devices SET fall_threshold = 0.6 WHERE fall_threshold = 0.25")
