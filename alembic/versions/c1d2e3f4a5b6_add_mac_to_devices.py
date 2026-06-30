"""add mac to devices

Revision ID: c1d2e3f4a5b6
Revises: a6efb11dc16b
Create Date: 2026-06-28 00:00:00.000000

Thêm cột `mac` (vân tay phần cứng = khóa topic MQTT). device_id trở thành id ngữ nghĩa
do backend sinh khi auto-provision; mac unique để khớp MQTT đến với bản ghi.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1d2e3f4a5b6'
down_revision = 'a6efb11dc16b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('devices', sa.Column('mac', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_devices_mac'), 'devices', ['mac'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_devices_mac'), table_name='devices')
    op.drop_column('devices', 'mac')
