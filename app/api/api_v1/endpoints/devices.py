from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
from uuid import UUID

from app.db.session import get_db
from app.models.domain import Device, Wearer
from app.schemas.domain import DeviceCreate, DeviceResponse, DeviceAssign

router = APIRouter()

@router.get("/", response_model=List[DeviceResponse])
async def read_devices(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """Lấy danh sách thiết bị kèm thông tin người đeo (nếu có)."""
    # Use selectinload to fetch the related wearer efficiently
    result = await db.execute(
        select(Device).options(selectinload(Device.wearer)).offset(skip).limit(limit)
    )
    devices = result.scalars().all()
    return devices

@router.post("/", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def create_device(device_in: DeviceCreate, db: AsyncSession = Depends(get_db)):
    """Đăng ký thiết bị phần cứng mới."""
    # Check if device already exists
    result = await db.execute(select(Device).where(Device.device_id == device_in.device_id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Device already registered")
        
    db_device = Device(**device_in.model_dump())
    db.add(db_device)
    await db.commit()
    await db.refresh(db_device)
    return db_device

@router.post("/{device_id}/assign", response_model=DeviceResponse)
async def assign_device(device_id: str, assign_in: DeviceAssign, db: AsyncSession = Depends(get_db)):
    """Gán thiết bị cho một bệnh nhân."""
    # 1. Lấy thiết bị
    result = await db.execute(select(Device).options(selectinload(Device.wearer)).where(Device.device_id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    # 2. Kiểm tra bệnh nhân có tồn tại không
    wearer_result = await db.execute(select(Wearer).where(Wearer.id == assign_in.wearer_id))
    wearer = wearer_result.scalar_one_or_none()
    if not wearer:
        raise HTTPException(status_code=404, detail="Wearer not found")
        
    # 3. Gán thiết bị
    device.current_wearer_id = wearer.id
    await db.commit()
    await db.refresh(device)
    return device

@router.post("/{device_id}/unassign", response_model=DeviceResponse)
async def unassign_device(device_id: str, db: AsyncSession = Depends(get_db)):
    """Gỡ thiết bị khỏi bệnh nhân hiện tại."""
    result = await db.execute(select(Device).options(selectinload(Device.wearer)).where(Device.device_id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    device.current_wearer_id = None
    await db.commit()
    await db.refresh(device)
    return device
