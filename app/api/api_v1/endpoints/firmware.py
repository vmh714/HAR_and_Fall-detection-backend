import hashlib
import os
import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.db.session import get_db
from app.api.deps import get_current_user, get_admin_user
from app.models.domain import Device, User, FirmwareRelease
from app.services.mqtt_service import mqtt_service
import json

router = APIRouter()

FIRMWARE_DIR = "static/firmware"


class FirmwareReleaseResponse(BaseModel):
    version: str
    release_date: str
    changelog: str
    is_stable: bool
    is_latest: bool
    bin_size: int
    sha256: str
    download_url: str
    model_config = ConfigDict(from_attributes=False)


class OtaUpdateRequest(BaseModel):
    version: str
    download_url: str


def _to_response(row: FirmwareRelease, base_url: str) -> FirmwareReleaseResponse:
    url = f"{base_url.rstrip('/')}static/firmware/{row.bin_filename}"
    return FirmwareReleaseResponse(
        version=row.version,
        release_date=row.release_date.isoformat(),
        changelog=row.changelog,
        is_stable=row.is_stable,
        is_latest=row.is_latest,
        bin_size=row.bin_size,
        sha256=row.sha256,
        download_url=url,
    )


@router.get("/versions", response_model=List[FirmwareReleaseResponse])
async def get_firmware_versions(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trả về danh sách phiên bản firmware có thể cập nhật OTA (đọc từ DB)."""
    result = await db.execute(
        select(FirmwareRelease).order_by(FirmwareRelease.created_at.desc())
    )
    rows = result.scalars().all()
    return [_to_response(r, str(request.base_url)) for r in rows]


@router.post("/upload", response_model=FirmwareReleaseResponse, status_code=201)
async def upload_firmware(
    request: Request,
    file: UploadFile = File(..., description="File firmware .bin"),
    version: str = Form(..., max_length=20),
    release_date: str = Form(..., description="YYYY-MM-DD"),
    changelog: str = Form(...),
    is_stable: bool = Form(True),
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """Upload firmware .bin mới (ADMIN only). Tự tính SHA256, lưu file, insert DB."""
    # Validate version chưa tồn tại
    existing = await db.execute(
        select(FirmwareRelease).where(FirmwareRelease.version == version)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Version {version} đã tồn tại")

    # Validate file extension
    if not (file.filename or "").endswith(".bin"):
        raise HTTPException(status_code=422, detail="Chỉ chấp nhận file .bin")

    # Đọc file và tính SHA256
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=422, detail="File không được rỗng")

    sha256 = hashlib.sha256(content).hexdigest()
    bin_filename = f"firmware_v{version}_{sha256[:8]}.bin"
    file_path = os.path.join(FIRMWARE_DIR, bin_filename)

    # Lưu file vào static/firmware/
    os.makedirs(FIRMWARE_DIR, exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(content)

    # Unset is_latest cho tất cả version cũ
    old_rows = await db.execute(
        select(FirmwareRelease).where(FirmwareRelease.is_latest == True)
    )
    for old in old_rows.scalars().all():
        old.is_latest = False

    # Parse release_date
    try:
        parsed_date = datetime.date.fromisoformat(release_date)
    except ValueError:
        raise HTTPException(status_code=422, detail="release_date phải có định dạng YYYY-MM-DD")

    # Insert DB record
    release = FirmwareRelease(
        id=uuid.uuid4(),
        version=version,
        release_date=parsed_date,
        changelog=changelog,
        is_stable=is_stable,
        is_latest=True,
        bin_filename=bin_filename,
        bin_size=len(content),
        sha256=sha256,
    )
    db.add(release)
    await db.commit()

    return _to_response(release, str(request.base_url))


@router.post("/{device_id}/update")
async def trigger_ota_update(
    device_id: str,
    body: OtaUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Gửi lệnh OTA xuống thiết bị qua MQTT. Thiết bị tự tải firmware từ download_url
    rồi flash vào OTA partition và restart. Backend không chờ kết quả."""
    result = await db.execute(
        select(Device).where(
            Device.device_id == device_id,
            Device.org_id == current_user.org_id,
        )
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if not device.mac:
        raise HTTPException(status_code=409, detail="Device chưa online (chưa có MAC) — không gửi OTA được.")

    # Validate version tồn tại trong DB
    ver_result = await db.execute(
        select(FirmwareRelease).where(FirmwareRelease.version == body.version)
    )
    if not ver_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Firmware version {body.version} không tồn tại")

    if not mqtt_service.client:
        raise HTTPException(status_code=503, detail="MQTT bridge chưa kết nối")

    payload = json.dumps({"action": "ota_update", "url": body.download_url})
    try:
        # Topic key = MAC (vân tay phần cứng)
        await mqtt_service.client.publish(
            f"eldercare/{device.mac}/command",
            payload=payload,
            qos=1,
            retain=False,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Publish OTA command thất bại: {e}")

    return {"ok": True, "device_id": device_id, "target_version": body.version}
