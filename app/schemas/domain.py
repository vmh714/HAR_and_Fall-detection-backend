from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from uuid import UUID
from datetime import datetime

# ==========================================
# WEARER SCHEMAS
# ==========================================
class WearerBase(BaseModel):
    full_name: str = Field(..., max_length=100, description="Họ và tên người bệnh")
    height_cm: float = Field(..., gt=0, description="Chiều cao (cm) để tính toán quãng đường")

class WearerCreate(WearerBase):
    org_id: UUID = Field(..., description="ID của Viện dưỡng lão/Tổ chức")

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
    pass

class DeviceAssign(BaseModel):
    wearer_id: UUID = Field(..., description="ID của người bệnh cần gán")

class DeviceResponse(DeviceBase):
    current_wearer_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime
    
    # Nested response for wearer details (optional)
    wearer: Optional[WearerResponse] = None

    model_config = ConfigDict(from_attributes=True)
