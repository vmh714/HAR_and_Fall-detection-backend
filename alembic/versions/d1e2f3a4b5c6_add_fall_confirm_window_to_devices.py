"""Add fall_confirm_window to devices

Revision ID: d1e2f3a4b5c6
Revises: c1d2e3f4a5b6
Create Date: 2026-06-29 00:00:00.000000

Thêm cột `fall_confirm_window` (giây): cửa sổ xác nhận post-impact trước khi bắn alert ngã.
Firmware quan sát N giây sau ML trigger rồi mới confirm — loại báo giả mà không mất recall.
Default 4s, range 1–15, cấu hình từ xa qua PUT /devices/{id} → MQTT config/set.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, Sequence[str], None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('devices', sa.Column('fall_confirm_window', sa.Integer(), server_default='4', nullable=False))


def downgrade() -> None:
    op.drop_column('devices', 'fall_confirm_window')
