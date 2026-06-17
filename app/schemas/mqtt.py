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
    walk_steps: int = 0
    run_steps: int = 0
    ai_pred: str = "UNKNOWN"
    ai_conf: float = 0.0
    interval: Optional[int] = None

class AlertPayload(MQTTBase):
    # confidence là field DUY NHẤT backend dùng (process_alert). user_name/message
    # để optional: firmware/giả lập có thể bỏ qua mà alert "sống còn" vẫn được ghi.
    confidence: float
    user_name: Optional[str] = None
    message: Optional[str] = None

class EventPayload(MQTTBase):
    event_type: str
    description: Optional[str] = None
