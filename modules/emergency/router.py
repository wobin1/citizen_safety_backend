from fastapi import APIRouter, Depends, Query
from .models import EmergencySubmit, EmergencyValidate, EmergencyReject
from .manager import submit_emergency, validate_emergency, get_emergencies, get_emergency, reject_emergency, get_emergency_stats, mark_action_taken
from typing import Optional, Dict
from modules.auth.manager import get_current_user

router = APIRouter()

@router.post("/submit")
async def submit(emergency: EmergencySubmit, current_user: dict = Depends(get_current_user)):
    """Submit a new emergency report"""
    return await submit_emergency(emergency, current_user)

@router.post("/{emergency_id}/validate")
async def validate(emergency_id: str, validation: EmergencyValidate, current_user: dict = Depends(get_current_user)):
    """Validate or update an emergency"""
    return await validate_emergency(emergency_id, validation, current_user)

@router.post("/{emergency_id}/action-taken")
async def action_taken(emergency_id: str, current_user: dict = Depends(get_current_user)):
    """Mark an emergency as action taken"""
    return await mark_action_taken(emergency_id, current_user)

@router.get("/")
async def get_all_emergencies(
    search: str = Query(None),
    status: str = Query(None),
    severity: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Get all emergencies with optional filters"""
    filters = {}
    if search:
        filters['search'] = search
    if status:
        filters['status'] = status
    if severity:
        filters['severity'] = severity
    filters['page'] = page
    filters['page_size'] = page_size
    return await get_emergencies(filters, current_user)

@router.get("/{emergency_id}")
async def get_single_emergency(emergency_id: str, current_user: dict = Depends(get_current_user)):
    """Get a single emergency by ID"""
    return await get_emergency({"id": emergency_id}, current_user)

@router.post("/{emergency_id}/reject")
async def reject_emergency_endpoint(
    emergency_id: str,
    body: EmergencyReject,   
    current_user: dict = Depends(get_current_user)
):
    """Reject an emergency by ID"""
    rejection_reason = body.rejection_reason
    if not rejection_reason:
        return {"status": "error", "message": "Rejection reason is required", "data": None}
    return await reject_emergency(emergency_id, rejection_reason, current_user)

@router.get("/stats/dashboard")
async def get_stats(current_user: dict = Depends(get_current_user)):
    """Get emergency statistics"""
    return await get_emergency_stats(current_user)