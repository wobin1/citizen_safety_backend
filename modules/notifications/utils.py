import asyncio
from typing import Dict, Set
from fastapi import WebSocket


class ConnectionManager:
    """Simple in-memory WebSocket connection manager grouped by topics."""
    def __init__(self) -> None:
        self._topic_to_connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, topic: str) -> None:
        await websocket.accept()
        async with self._lock:
            self._topic_to_connections.setdefault(topic, set()).add(websocket)

    async def disconnect(self, websocket: WebSocket, topic: str) -> None:
        async with self._lock:
            conns = self._topic_to_connections.get(topic)
            if conns and websocket in conns:
                conns.remove(websocket)
                if not conns:
                    self._topic_to_connections.pop(topic, None)

    async def broadcast(self, topic: str, message: dict) -> None:
        # Copy to avoid size change during iteration
        connections = list(self._topic_to_connections.get(topic, set()))
        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception:
                # Best-effort cleanup on broken connection
                await self.disconnect(ws, topic)


manager = ConnectionManager()

def topic_for_user(user_id: str) -> str:
    return f"user:{user_id}"

def topic_broadcast_all() -> str:
    return "broadcast:all"


