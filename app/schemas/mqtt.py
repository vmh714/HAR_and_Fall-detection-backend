from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional

class MQTTBase(BaseModel):
    device_id: str
    timestamp: Optional[int] = None
    
    model_config = ConfigDict(populate_by_name=True)

class StatusPayload(MQTTBase):
    state: str = "NORMAL"
    battery_pct: int = Field(alias="battery")
    rssi: Optional[int] = None
    steps: int = 0
    ai_pred: str = "UNKNOWN"
    ai_conf: float = 0.0
    interval: Optional[int] = None

class AlertPayload(MQTTBase):
    user_name: str
    confidence: float
    message: str

class EventPayload(MQTTBase):
    event_type: str
    description: Optional[str] = None
