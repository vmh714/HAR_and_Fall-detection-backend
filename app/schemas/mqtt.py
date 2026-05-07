from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class MQTTBase(BaseModel):
    device_id: str
    timestamp: Optional[int] = None

class StatusPayload(MQTTBase):
    status: str = "online"
    battery_pct: int
    rssi: Optional[int] = None
    walk_steps: int = 0
    run_steps: int = 0

class AlertPayload(MQTTBase):
    user_name: str
    confidence: float
    message: str

class EventPayload(MQTTBase):
    event_type: str
    description: Optional[str] = None
