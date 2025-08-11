from typing import Optional, Dict
from .utils import manager, topic_for_user, topic_broadcast_all


async def notify_user(user_id: str, event: str, data: Dict) -> None:
    await manager.broadcast(topic_for_user(user_id), {"event": event, "data": data})


async def notify_broadcast(event: str, data: Dict) -> None:
    await manager.broadcast(topic_broadcast_all(), {"event": event, "data": data})


