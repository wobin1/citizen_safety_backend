from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class AlertTrigger(BaseModel):
    trigger_source: str
    type: str
    message: str
    location_lat: float
    location_lon: Optional[float]
    radius_km: float
    broadcast_type: str

class AlertResponse(BaseModel):
    id: UUID
    trigger_source: str
    type: str
    message: str
    location_lat: float
    location_lon: Optional[float]
    radius_km: float
    status: str
    created_at: str
    cooldown_until: Optional[str]