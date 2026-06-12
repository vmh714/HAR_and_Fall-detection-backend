from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional

class MQTTBase(BaseModel):
    device_id: str
    timestamp: Optional[int] = None
    
    model_config = ConfigDict(populate_by_name=True)

class StatusPayload(MQTTBase):
    status: str = "online"
    battery_pct: int = Field(alias="battery")
    rssi: Optional[int] = None
    walk_steps: int = Field(default=0, alias="steps")
    run_steps: int = 0

class AlertPayload(MQTTBase):
    user_name: str
    confidence: float
    message: str

class EventPayload(MQTTBase):
    event_type: str
    description: Optional[str] = None
