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

class IncidentReject(BaseModel):
    rejection_reason: str

class EmergencySubmit(BaseModel):
    type: str
    description: str
    location_lat: float
    location_lon: float
    severity: str
    image_url: Optional[str]
    voice_note_url: Optional[str]
    video_url: Optional[str]

class EmergencyValidate(BaseModel):
    status: str
    rejection_reason: Optional[str]
    responder_id: Optional[UUID]

class EmergencyResponse(BaseModel):
    id: UUID
    user_id: UUID
    type: str
    description: str
    location_lat: float
    location_lon: float
    severity: str
    status: str
    created_at: str
    updated_at: Optional[str]
    validated_at: Optional[str]
    responder_id: Optional[UUID]
    response_time: Optional[str]
    rejection_reason: Optional[str]
    user_name: Optional[str]
    responder_name: Optional[str]

class EmergencyReject(BaseModel):
    rejection_reason: str