from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class IncidentSubmit(BaseModel):
    type: str
    description: str
    location_lat: Optional[float]
    location_lon: Optional[float]

class IncidentValidate(BaseModel):
    status: str
    rejection_reason: Optional[str]

class IncidentResponse(BaseModel):
    id: UUID
    user_id: UUID
    type: str
    description: str
    location_lat: Optional[float]
    location_lon: Optional[float]
    status: str
    created_at: str
    validated_at: Optional[str]
    rejection_reason: Optional[str]