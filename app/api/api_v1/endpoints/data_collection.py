from fastapi import APIRouter, status, Depends, HTTPException
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.schemas.data_collection import DataCollectionSessionCreate
from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.domain import Device, User
from app.db.influx_client import influx_manager
from influxdb_client import Point
from app.core.config import settings

router = APIRouter()

@router.post("/sessions", status_code=status.HTTP_201_CREATED)
async def save_data_collection_session(
    session: DataCollectionSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Nhận dữ liệu thu thập từ Frontend và lưu vào InfluxDB measurement 'imu_raw'.
    Định dạng dữ liệu được tối ưu để huấn luyện TinyML sau này.
    """
    # Chỉ cho ghi dữ liệu cho thiết bị thuộc tổ chức của user (chống ghi giả mạo).
    device = await db.execute(
        select(Device).where(Device.device_id == session.device_id, Device.org_id == current_user.org_id)
    )
    if not device.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Device not found")

    session_id = str(uuid4())
    points = []
    for sample in session.samples:
        point = Point("imu_raw") \
            .tag("device_id", session.device_id) \
            .tag("label", session.label) \
            .tag("session_id", session_id) \
            .field("ax", sample.ax) \
            .field("ay", sample.ay) \
            .field("az", sample.az) \
            .field("gx", sample.gx) \
            .field("gy", sample.gy) \
            .field("gz", sample.gz) \
            .time(sample.timestamp, write_precision='ms')
        points.append(point)

    try:
        influx_manager.write_api.write(bucket=settings.INFLUXDB_BUCKET, record=points)
    except Exception as e:
        print(f"Error writing to InfluxDB: {e}")

    return {
        "status": "success",
        "message": "Data collection session saved",
        "session_id": session_id,
        "sample_count": len(points),
        "device_id": session.device_id,
        "label": session.label
    }
