from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Request
from .models import AlertTrigger, AlertResponse
from .manager import trigger_alert, resolve_alert, get_all_active_alerts, get_all_alerts
from modules.auth.manager import get_current_user
from modules.shared.response import success_response, error_response
from uuid import uuid4
from datetime import datetime, timedelta
from typing import List, Dict, Any
import json
import logging
from modules.shared.db import execute_query
from .manager import connected_alert_clients

# Set up logger
logger = logging.getLogger(__name__)

# Store client info: {websocket: {"location": (lat, lon), "user_id": ...}}

router = APIRouter()

@router.post("/trigger")
async def trigger(trigger: AlertTrigger, current_user: dict = Depends(get_current_user)):
    logger.debug(f"Trigger endpoint called by user: {current_user} with trigger: {trigger}")
    return await trigger_alert(trigger, current_user)

@router.post("/{alert_id}/resolve")
async def resolve(alert_id: str, current_user: dict = Depends(get_current_user)):
    logger.debug(f"Resolve endpoint called by user: {current_user} for alert_id: {alert_id}")
    return await resolve_alert(alert_id, current_user)

@router.get("/")
# async def get_active_alerts(current_user: dict = Depends(get_current_user)):
async def get_active_alerts():
    logger.debug("Get active alerts endpoint called")
    # return await get_alerts(current_user)
    return await get_all_active_alerts()

@router.get("/all")
async def get_all_alerts_endpoint(
    status: str = None,
    search: str = None,
    page: int = 1,
    page_size: int = 10
):
    """
    Get all alerts with optional filters and pagination.
    Query parameters:
        - status: filter by alert status (e.g., 'ACTIVE', 'RESOLVED')
        - search: filter by type or message (case-insensitive, partial match)
        - page: page number (default 1)
        - page_size: number of items per page (default 10)
    """
    filters = {
        "status": status,
        "search": search,
        "page": page,
        "page_size": page_size
    }
    # Remove None values to avoid passing them as filters
    filters = {k: v for k, v in filters.items() if v is not None}
    from .manager import get_all_alerts
    return await get_all_alerts(filters)

@router.get("/{alert_id}")
async def get_alert_by_id_endpoint(alert_id: str):
    """
    Get a single alert by its ID.
    """
    from .manager import get_alert_by_id
    return await get_alert_by_id(alert_id)


@router.post("/register-fcm-token")
async def register_fcm_token(request: Request, current_user: dict = Depends(get_current_user)):
    data = await request.json()
    fcm_token = data.get("fcm_token")
    if not fcm_token:
        return error_response("Missing fcm_token", 400)
    user_id = current_user.get("id")
    if not user_id:
        return error_response("User not authenticated", 401)
    # Update the user's FCM token in the database
    query = "UPDATE users SET fcm_token = $1 WHERE id = $2"
    await execute_query(query, (fcm_token, user_id), commit=True)
    return success_response({}, "FCM token registered successfully")

@router.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    logger.info("WebSocket connection requested")
    await websocket.accept()
    connected_alert_clients[websocket] = {"location": None, "user_id": None}
    logger.debug(f"WebSocket client connected: {websocket.client}")
    try:
        while True:
            data = await websocket.receive_text()
            logger.debug(f"Received data from WebSocket client: {data}")
            try:
                msg = json.loads(data)
                if msg.get("type") == "register_location":
                    lat = msg.get("lat")
                    lon = msg.get("lon")
                    user_id = msg.get("user_id")
                    connected_alert_clients[websocket]["location"] = (lat, lon)
                    connected_alert_clients[websocket]["user_id"] = user_id
                    logger.info(f"Registered location for user_id={user_id}: lat={lat}, lon={lon}")
            except Exception as e:
                logger.warning(f"Malformed message from WebSocket client: {data}, error: {e}")
                pass  # Ignore malformed messages
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: {websocket.client}")
        connected_alert_clients.pop(websocket, None)