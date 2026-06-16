from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Optional, Literal

class TimelineEntry(BaseModel):
    id: UUID
    type: Literal["ALERT", "EVENT"]
    title: str
    description: Optional[str] = None
    created_at: datetime

class AlertHistory(BaseModel):
    id: UUID
    device_id: str
    alert_type: str
    confidence: float
    is_resolved: bool
    created_at: datetime

    model_config = {"from_attributes": True}

class StepHistoryResponse(BaseModel):
    date: str
    steps: int
    distance_km: float

class TelemetryHistoryResponse(BaseModel):
    timestamp: datetime
    battery_pct: Optional[float] = None
    steps: Optional[int] = None
    distance_m: Optional[float] = None
    state: Optional[str] = None
    ai_pred: Optional[str] = None
    ai_conf: Optional[float] = None
    rssi: Optional[int] = None
