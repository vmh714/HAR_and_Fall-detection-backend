from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.domain import Device, User
from app.api.deps import get_current_user
from typing import List

router = APIRouter()

@router.get("/telemetry")
async def get_dashboard_telemetry(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetch current status of all devices (battery, online status).
    Note: Step counts are in InfluxDB and will be added in Phase 2.
    """
    result = await db.execute(
        select(Device).where(Device.org_id == current_user.org_id)
    )
    devices = result.scalars().all()
    
    return [
        {
            "device_id": d.device_id,
            "battery_pct": d.battery_pct,
            "last_rssi": d.last_rssi,
            "last_online": d.last_online,
            "is_active": d.is_active,
            "wearer_id": d.current_wearer_id
        }
        for d in devices
    ]
