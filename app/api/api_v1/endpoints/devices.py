from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
from uuid import UUID

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.domain import Device, Wearer, User
from app.schemas.domain import DeviceCreate, DeviceResponse, DeviceAssign, DeviceUpdate, DeviceCommand
from app.services.mqtt_service import mqtt_service
import json

router = APIRouter()

@router.get("/", response_model=List[DeviceResponse])
async def read_devices(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0, 
    limit: int = 100
):
    """Lấy danh sách thiết bị của tổ chức kèm thông tin người đeo."""
    result = await db.execute(
        select(Device)
        .options(selectinload(Device.wearer))
        .where(Device.org_id == current_user.org_id)
        .offset(skip)
        .limit(limit)
    )
    devices = result.scalars().all()
    return devices

@router.post("/", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def create_device(
    device_in: DeviceCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Đăng ký thiết bị phần cứng mới cho tổ chức hiện tại."""
    # Check if device already exists
    result = await db.execute(select(Device).where(Device.device_id == device_in.device_id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Device already registered")
        
    device_data = device_in.model_dump()
    # Luôn ép org_id theo user hiện tại — KHÔNG cho client tự chỉ định org khác.
    device_data["org_id"] = current_user.org_id

    db_device = Device(**device_data)
    db.add(db_device)
    await db.commit()
    
    # Re-fetch with selectinload
    result = await db.execute(
        select(Device).options(selectinload(Device.wearer)).where(Device.device_id == db_device.device_id)
    )
    return result.scalar_one()

@router.get("/{device_id}", response_model=DeviceResponse)
async def read_device(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lấy thông tin chi tiết một thiết bị."""
    result = await db.execute(
        select(Device)
        .options(selectinload(Device.wearer))
        .where(Device.device_id == device_id, Device.org_id == current_user.org_id)
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.put("/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: str,
    device_in: DeviceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cập nhật thông tin thiết bị (chỉ trong tổ chức của user)."""
    result = await db.execute(
        select(Device).options(selectinload(Device.wearer))
        .where(Device.device_id == device_id, Device.org_id == current_user.org_id)
    )
    db_device = result.scalar_one_or_none()
    if not db_device:
        raise HTTPException(status_code=404, detail="Device not found")

    update_data = device_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_device, key, value)
        
    await db.commit()
    
    # Publish MQTT command nếu các tham số áp xuống thiết bị thay đổi.
    # retain=False: command là lệnh tức thời, không giữ lại để device reconnect replay.
    # Giá trị bền vững (interval, fall_threshold) được firmware lưu NVS.
    if mqtt_service.client:
        if "telemetry_interval" in update_data:
            try:
                payload = json.dumps({"action": "set_interval", "val": update_data["telemetry_interval"]})
                await mqtt_service.client.publish(f"eldercare/{device_id}/command", payload=payload, qos=1, retain=False)
            except Exception as e:
                print(f"Failed to publish set_interval: {e}")
        if "fall_threshold" in update_data:
            try:
                payload = json.dumps({"action": "set_fall_threshold", "val": update_data["fall_threshold"]})
                await mqtt_service.client.publish(f"eldercare/{device_id}/command", payload=payload, qos=1, retain=False)
            except Exception as e:
                print(f"Failed to publish set_fall_threshold: {e}")
        if "fall_cooldown" in update_data:
            try:
                payload = json.dumps({"action": "set_fall_cooldown", "val": update_data["fall_cooldown"]})
                await mqtt_service.client.publish(f"eldercare/{device_id}/command", payload=payload, qos=1, retain=False)
            except Exception as e:
                print(f"Failed to publish set_fall_cooldown: {e}")
    
    # Re-fetch with selectinload
    result = await db.execute(
        select(Device).options(selectinload(Device.wearer)).where(Device.device_id == device_id)
    )
    return result.scalar_one()

@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Xóa hoàn toàn thiết bị khỏi Database (chỉ trong tổ chức của user)."""
    result = await db.execute(
        select(Device).where(Device.device_id == device_id, Device.org_id == current_user.org_id)
    )
    db_device = result.scalar_one_or_none()
    if not db_device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    await db.delete(db_device)
    await db.commit()
    return None

ALLOWED_COMMANDS = {"start_stream", "stop_stream"}

@router.post("/{device_id}/command")
async def send_device_command(
    device_id: str,
    command: DeviceCommand,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Gửi lệnh điều khiển realtime xuống thiết bị qua MQTT (thay vì FE publish trực
    tiếp). Backend kiểm tra thiết bị thuộc org của user trước khi publish."""
    if command.action not in ALLOWED_COMMANDS:
        raise HTTPException(status_code=422, detail=f"action phải thuộc {sorted(ALLOWED_COMMANDS)}")

    result = await db.execute(
        select(Device).where(Device.device_id == device_id, Device.org_id == current_user.org_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Device not found")

    if not mqtt_service.client:
        raise HTTPException(status_code=503, detail="MQTT bridge chưa kết nối")

    payload = {"action": command.action}
    if command.val is not None:
        payload["val"] = command.val
    try:
        await mqtt_service.client.publish(
            f"eldercare/{device_id}/command", payload=json.dumps(payload), qos=1, retain=False
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Publish thất bại: {e}")

    return {"ok": True, "action": command.action, "device_id": device_id}

@router.post("/{device_id}/assign", response_model=DeviceResponse)
async def assign_device(
    device_id: str,
    assign_in: DeviceAssign,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Gán thiết bị cho một bệnh nhân (cả hai phải thuộc tổ chức của user)."""
    # 1. Lấy thiết bị (trong org)
    result = await db.execute(
        select(Device).options(selectinload(Device.wearer))
        .where(Device.device_id == device_id, Device.org_id == current_user.org_id)
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # 2. Kiểm tra bệnh nhân tồn tại VÀ cùng org (chống gán chéo tổ chức)
    wearer_result = await db.execute(
        select(Wearer).where(Wearer.id == assign_in.wearer_id, Wearer.org_id == current_user.org_id)
    )
    wearer = wearer_result.scalar_one_or_none()
    if not wearer:
        raise HTTPException(status_code=404, detail="Wearer not found")
        
    # 3. Gán thiết bị
    device.current_wearer_id = wearer.id
    await db.commit()
    
    # Re-fetch with selectinload
    result = await db.execute(
        select(Device).options(selectinload(Device.wearer)).where(Device.device_id == device_id)
    )
    return result.scalar_one()

@router.post("/{device_id}/unassign", response_model=DeviceResponse)
async def unassign_device(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Gỡ thiết bị khỏi bệnh nhân hiện tại (chỉ trong tổ chức của user)."""
    result = await db.execute(
        select(Device).options(selectinload(Device.wearer))
        .where(Device.device_id == device_id, Device.org_id == current_user.org_id)
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    device.current_wearer_id = None
    await db.commit()
    
    # Re-fetch with selectinload
    result = await db.execute(
        select(Device).options(selectinload(Device.wearer)).where(Device.device_id == device_id)
    )
    return result.scalar_one()
