from pydantic import BaseModel, Field, ConfigDict, computed_field
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timezone

# ==========================================
# WEARER SCHEMAS
# ==========================================
class WearerBase(BaseModel):
    full_name: str = Field(..., max_length=100, description="Họ và tên người bệnh")
    height_cm: float = Field(..., gt=0, description="Chiều cao (cm) để tính toán quãng đường")

class WearerCreate(WearerBase):
    org_id: Optional[UUID] = Field(None, description="ID của Tổ chức (Nếu để trống sẽ lấy theo User)")

class WearerUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=100)
    height_cm: Optional[float] = Field(None, gt=0)

class WearerResponse(WearerBase):
    id: UUID
    org_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ==========================================
# DEVICE SCHEMAS
# ==========================================
class DeviceBase(BaseModel):
    device_id: str = Field(..., max_length=100, description="MAC Address hoặc MQTT Client ID")
    firmware_version: Optional[str] = Field(None, max_length=50)
    is_active: bool = Field(True)

class DeviceCreate(DeviceBase):
    org_id: Optional[UUID] = Field(None, description="ID của Tổ chức (Nếu để trống sẽ lấy theo User)")

class DeviceAssign(BaseModel):
    wearer_id: UUID = Field(..., description="ID của người bệnh cần gán")

class DeviceUpdate(BaseModel):
    firmware_version: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = Field(None)

class DeviceResponse(DeviceBase):
    current_wearer_id: Optional[UUID]
    org_id: UUID
    created_at: datetime
    updated_at: datetime
    battery_pct: Optional[int] = None
    last_online: Optional[datetime] = None
    
    # Nested response for wearer details (optional)
    wearer: Optional[WearerResponse] = None

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    def is_online(self) -> bool:
        if not self.last_online:
            return False
        from app.core.config import settings
        now = datetime.now(timezone.utc)
        
        last_online_aware = self.last_online
        if last_online_aware.tzinfo is None:
            last_online_aware = last_online_aware.replace(tzinfo=timezone.utc)
            
        diff_seconds = (now - last_online_aware).total_seconds()
        return diff_seconds < settings.DEVICE_ONLINE_TIMEOUT_SECONDS
