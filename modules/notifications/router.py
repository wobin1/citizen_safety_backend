from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from .utils import manager, topic_for_user, topic_broadcast_all
from modules.auth.manager import get_current_user, decode_token
import json
import logging

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
    await websocket.accept()
    
    try:
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
        await manager.disconnect(websocket, topic)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close(code=4000, reason="Internal error")


