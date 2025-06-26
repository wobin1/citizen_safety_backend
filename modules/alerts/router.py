from fastapi import APIRouter, Depends
from .models import AlertTrigger, AlertResponse
from .manager import trigger_alert, resolve_alert, get_alerts
from modules.auth.manager import get_current_user
from modules.shared.response import success_response, error_response
from uuid import uuid4
from datetime import datetime, timedelta

router = APIRouter()

@router.post("/trigger")
async def trigger(trigger: AlertTrigger, current_user: dict = Depends(get_current_user)):
    return await trigger_alert(trigger, current_user)

@router.post("/{alert_id}/resolve")
async def resolve(alert_id: str, current_user: dict = Depends(get_current_user)):
    return await resolve_alert(alert_id, current_user)

@router.get("/")
async def get_active_alerts(current_user: dict = Depends(get_current_user)):
    return await get_alerts(current_user)