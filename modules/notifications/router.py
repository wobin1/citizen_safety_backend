from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from .utils import manager, topic_for_user, topic_broadcast_all
from modules.auth.manager import get_current_user, decode_token
from .manager import notify_emergency_service_and_admin
import json
import logging
from fastapi import Depends
from fastapi.responses import JSONResponse
from fastapi import status

from modules.auth.manager import get_current_user


logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def ws_notifications(websocket: WebSocket, topic: str = Query(topic_broadcast_all())):
    await manager.connect(websocket, topic)
    try:
        while True:
            # Keep connection alive; messages from client are ignored
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket, topic)


@router.websocket("/ws/me")
async def ws_notifications_me(websocket: WebSocket):
    topic = None
    try:
        await websocket.accept()
        
        # Wait for the first message which should contain the token
        first_message = await websocket.receive_text()
        token_data = json.loads(first_message)
        token = token_data.get("token")
        
        if not token:
            await websocket.close(code=4001, reason="No token provided")
            return
        
        # Validate the token manually
        try:
            payload = decode_token(token)
            user_id = payload["sub"]
        except Exception as e:
            logger.error(f"Invalid token in WebSocket connection: {e}")
            await websocket.close(code=4001, reason="Invalid token")
            return
        
        # Connect to user-specific topic
        topic = topic_for_user(user_id)
        await manager.connect(websocket, topic)
        
        # Keep connection alive
        while True:
            await websocket.receive_text()
            
    except WebSocketDisconnect:
        if topic:
            await manager.disconnect(websocket, topic)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if topic:
            await manager.disconnect(websocket, topic)
        try:
            await websocket.close(code=4000, reason="Internal error")
        except:
            pass


@router.get("/all")
async def get_my_notifications(current_user=Depends(get_current_user)):
    """
    Get all notifications for the current user.
    """
    notifications = await get_all_notifications(current_user.id)
    return notifications

@router.post("/send-notice")
async def send_notification():
    await notify_emergency_service_and_admin("hello world", {"test": "this is a test"})
