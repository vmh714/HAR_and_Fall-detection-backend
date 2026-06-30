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

class ConfigStatusPayload(MQTTBase):
    interval: Optional[int] = None
    fall_threshold: Optional[float] = None
    fall_cooldown: Optional[int] = None
    fall_confirm_window: Optional[int] = None
    stream_timeout: Optional[int] = None
    rssi_interval: Optional[int] = None
    fw_version: Optional[str] = None  # firmware tự báo version đang chạy (lúc connect/reconnect)

class AlertPayload(MQTTBase):
    # confidence là field DUY NHẤT backend dùng (process_alert). user_name/message
    # để optional: firmware/giả lập có thể bỏ qua mà alert "sống còn" vẫn được ghi.
    confidence: float
    user_name: Optional[str] = None
    message: Optional[str] = None

class EventPayload(MQTTBase):
    event_type: str
    description: Optional[str] = None
