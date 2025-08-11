from typing import Optional, Dict, List
from .utils import manager, topic_for_user, topic_broadcast_all
from modules.shared.db import execute_query
import logging

logger = logging.getLogger(__name__)


def serialize_row(row):
            d = dict(row)
            for k, v in d.items():
                if isinstance(v, datetime):
                    d[k] = v.isoformat()
            return d


async def notify_user(user_id: str, event: str, data: Dict) -> None:
    logger.info(f"Sending notification to user {user_id}: event={event}, data={data}")
    await manager.broadcast(topic_for_user(user_id), {"event": event, "data": data})


async def notify_broadcast(event: str, data: Dict) -> None:
    logger.info(f"Broadcasting notification to all users: event={event}, data={data}")
    await manager.broadcast(topic_broadcast_all(), {"event": event, "data": data})


async def get_users_by_role(role: str) -> List[str]:
    """Get all user IDs for a specific role."""
    try:
        logger.debug(f"Fetching users with role: {role}")
        result = await execute_query(
            "SELECT id FROM users WHERE role = $1",
            (role,),
            fetch_all=True
        )
        user_ids = [row[0] for row in result] if result else []
        logger.info(f"Found {len(user_ids)} users with role '{role}'")
        return user_ids
    except Exception as e:
        logger.error(f"Error getting users by role {role}: {e}")
        return []


async def notify_role(role: str, event: str, data: Dict) -> None:
    """Send notification to all users with a specific role."""
    user_ids = await get_users_by_role(role)
    logger.info(f"Sending notification to role '{role}' ({len(user_ids)} users): event={event}, data={data}")
    for user_id in user_ids:
        await notify_user(user_id, event, data)


async def notify_emergency_service_and_admin(event: str, data: Dict) -> None:
    """Send notification to all emergency service and admin users."""
    emergency_service_users = await get_users_by_role('emergency_service')
    admin_users = await get_users_by_role('admin')
    
    all_users = emergency_service_users + admin_users
    logger.info(f"Sending notification to emergency_service and admin users ({len(all_users)} users): event={event}, data={data}")
    for user_id in all_users:
        await notify_user(user_id, event, data)


async def get_all_notifications() -> List[Dict]:
    """
    Retrieve all notifications from the database.
    Returns:
        List[Dict]: A list of notification records as dictionaries.
    """
    try:
        logger.debug("Fetching all notifications from the database")
        result = await execute_query(
            "SELECT id, user_id, event, data, timestamp, read FROM notifications",
            (),
            fetch_all=True
        )
        notifications = [
                            serialize_row(r)
                            for r in results
                        ]
        logger.info(f"Fetched {len(notifications)} notifications")
        return notifications
    except Exception as e:
        logger.error(f"Error fetching all notifications: {e}")
        return []
