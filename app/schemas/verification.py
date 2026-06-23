from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class VerificationSessionCreate(BaseModel):
    device_id: str
    subject_code: str   # "SV01"
    activity_code: str  # "D01"
    trial_no: str       # "R01"


class VerificationSessionData(BaseModel):
    session_id: UUID
    samples: List[List[float]]  # [[ax,ay,az,gx,gy,gz], ...] đơn vị g và deg/s


class VerificationSessionResponse(BaseModel):
    id: UUID
    device_id: str
    subject_code: str
    activity_code: str
    trial_no: str
    sample_count: Optional[int] = None
    duration_s: Optional[float] = None
    file_path: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
