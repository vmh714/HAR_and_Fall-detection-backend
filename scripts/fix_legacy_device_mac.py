"""One-off migration: gộp thiết bị auto-provision nhầm (esp32_eldercare_02) vào bản ghi
legacy (esp32_eldercare_01) để giữ device_id + toàn bộ lịch sử (Postgres + InfluxDB).

Chạy: cd backend && har_env/Scripts/python.exe scripts/fix_legacy_device_mac.py [TARGET_DEVICE_ID]
Mặc định TARGET = esp32_eldercare_01. Source = device duy nhất có mac != NULL và khác TARGET.
"""
import sys
import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.domain import Device

TARGET = sys.argv[1] if len(sys.argv) > 1 else "esp32_eldercare_01"


async def main():
    async with AsyncSessionLocal() as db:
        tgt = (await db.execute(select(Device).where(Device.device_id == TARGET))).scalar_one_or_none()
        if tgt is None:
            print(f"[ABORT] Target '{TARGET}' không tồn tại")
            return

        src = (await db.execute(
            select(Device).where(Device.mac.isnot(None), Device.device_id != TARGET)
        )).scalars().all()
        if len(src) != 1:
            print(f"[ABORT] Cần đúng 1 device có mac (khác target), thấy {len(src)}: "
                  f"{[(s.device_id, s.mac) for s in src]}")
            return

        s = src[0]
        mac, fw = s.mac, s.firmware_version
        print(f"Merge: {s.device_id} (mac={mac}, fw={fw}) → {TARGET}")

        # Xoá bản ghi auto-tạo nhầm trước (giải phóng unique mac), rồi gắn mac+fw lên target.
        await db.delete(s)
        await db.flush()
        tgt.mac = mac
        tgt.firmware_version = fw
        tgt.is_active = True
        await db.commit()
        print(f"[OK] Đã xoá {s.device_id}; {TARGET} nay có mac={mac}, fw={fw}, is_active=True")


asyncio.run(main())
