from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from .models import IncidentSubmit, IncidentValidate, IncidentResponse, IncidentReject
from .manager import submit_incident, submit_incident_with_files, validate_incident, get_incidents, get_incident, reject_incident
from typing import Optional, Dict
from modules.auth.manager import get_current_user

router = APIRouter()

@router.post("/submit")
async def submit(
    incident: IncidentSubmit | None = None,
    type: str | None = Form(None),
    description: str | None = Form(None),
    location_lat: float | None = Form(None),
    location_lon: float | None = Form(None),
    image: UploadFile | None = File(None),
    voice_note: UploadFile | None = File(None),
    video: UploadFile | None = File(None),
    current_user: dict = Depends(get_current_user)
):
    # JSON path
    if incident is not None:
        return await submit_incident(incident, current_user)
    # Multipart path
    if not all([type, description, location_lat is not None, location_lon is not None]):
        return {"status": "error", "message": "Missing required fields", "data": None}
    return await submit_incident_with_files(
        type=type, description=description,
        location_lat=float(location_lat), location_lon=float(location_lon),
        image=image, voice_note=voice_note, video=video,
        current_user=current_user,
    )

@router.post("/{incident_id}/validate")
async def validate(incident_id: str, validation: IncidentValidate, current_user: dict = Depends(get_current_user)):
    return await validate_incident(incident_id, validation, current_user)

@router.get("/")
async def get_all_incidents(
    search: str = Query(None),
    status: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    filters = {}
    if search:
        filters['search'] = search
    if status:
        filters['status'] = status
    filters['page'] = page
    filters['page_size'] = page_size
    return await get_incidents(filters, current_user)

@router.get("/{incident_id}")
async def get_single_incident(incident_id: str, current_user: dict = Depends(get_current_user)):
    return await get_incident({"id": incident_id}, current_user)

@router.post("/{incident_id}/reject")
async def reject_incident_endpoint(
    incident_id: str,
    body: IncidentReject,   
    current_user: dict = Depends(get_current_user)
):
    """
    Endpoint to reject an incident by ID.
    Expects JSON body: { "rejection_reason": "reason here" }
    """
    rejection_reason = body.rejection_reason
    if not rejection_reason:
        return {"status": "error", "message": "Rejection reason is required", "data": None}
    return await reject_incident(incident_id, rejection_reason, current_user)

@router.get("/stats/dashboard")
async def get_stats(current_user: dict = Depends(get_current_user)):
    from .manager import get_incident_stats
    return await get_incident_stats(current_user)

