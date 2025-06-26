from fastapi import APIRouter, Depends
from .models import IncidentSubmit, IncidentValidate, IncidentResponse
from .manager import submit_incident, validate_incident, get_incidents, get_incident
from typing import Optional, Dict
from modules.auth.manager import get_current_user
router = APIRouter()

@router.post("/submit")
async def submit(incident: IncidentSubmit, current_user: dict = Depends(get_current_user)):
    return await submit_incident(incident, current_user)

@router.post("/{incident_id}/validate")
async def validate(incident_id: str, validation: IncidentValidate, current_user: dict = Depends(get_current_user)):
    return await validate_incident(incident_id, validation, current_user)

@router.get("/")
async def get_all_incidents( current_user: dict = Depends(get_current_user)):
    return await get_incidents([], current_user)

@router.get("/{incident_id}")
async def get_single_incident(incident_id: str, current_user: dict = Depends(get_current_user)):
    return await get_incident({"id": incident_id}, current_user)