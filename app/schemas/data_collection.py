from pydantic import BaseModel, Field
from typing import List
from datetime import datetime

class IMUSampleSchema(BaseModel):
    timestamp: int = Field(..., description="Unix timestamp in ms")
    ax: float
    ay: float
    az: float
    gx: float
    gy: float
    gz: float

class DataCollectionSessionCreate(BaseModel):
    device_id: str
    label: str
    start_timestamp: int
    end_timestamp: int
    sample_count: int
    samples: List[IMUSampleSchema]
