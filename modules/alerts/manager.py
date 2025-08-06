import logging
from uuid import uuid4
from datetime import datetime, timedelta
from fastapi import Depends
from .models import AlertTrigger, AlertResponse
# --- Firebase Push Notification Integration ---
import firebase_admin  # Firebase A
from firebase_admin import credentials, messaging
import os
from fastapi import WebSocket
from typing import Any
import json

# Initialize Firebase app (only once)
if not firebase_admin._apps:
    firebase_credentials_json = os.getenv("FIREBASE_CREDENTIALS")
    if not firebase_credentials_json:
        raise RuntimeError("FIREBASE_CREDENTIALS not set")

    cred_dict = json.loads(firebase_credentials_json)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)

from modules.shared.db import execute_query
from modules.shared.response import success_response, error_response
from modules.auth.manager import get_current_user

import json
import math

logger = logging.getLogger(__name__)

connected_alert_clients: dict[WebSocket, dict[str, Any]] = {}


def serialize_row(row):
            d = dict(row)
            for k, v in d.items():
                if isinstance(v, datetime):
                    d[k] = v.isoformat()
            return d

# Haversine formula for distance in km
def haversine(lat1, lon1, lat2, lon2):
    logger.debug(f"Calculating haversine distance: ({lat1}, {lon1}) <-> ({lat2}, {lon2})")
    R = 6371  # Earth radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    distance = R * c
    logger.debug(f"Haversine distance result: {distance} km")
    return distance

async def get_all_fcm_tokens():
    # Fetch all non-null FCM tokens from the users table
    query = "SELECT fcm_token FROM users WHERE fcm_token IS NOT NULL"
    logger.debug("Fetching all FCM tokens from users table")
    results = await execute_query(query)
    tokens = [row[0] for row in results if row[0]]
    logger.debug(f"Fetched {len(tokens)} FCM tokens")
    return tokens

async def send_push_sms_email_to_all(alert_data):
    logger.info("Preparing to send push notifications to all users")
    tokens = await get_all_fcm_tokens()
    if not tokens:
        logger.warning("No FCM tokens to send push notifications.")
        print("No FCM tokens to send push notifications.")
        return
    # Create the notification message
    logger.debug(f"Sending push notification with alert_data: {alert_data}")
    message = messaging.MulticastMessage(
        notification=messaging.Notification(
            title="Emergency Alert",
            body=alert_data.get("message", "An alert has been triggered!"),
        ),
        data={k: str(v) for k, v in alert_data.items()},
        tokens=tokens,
    )
    # Send the notification
    try:
        response = messaging.send_multicast(message)
        logger.info(f"Successfully sent push notifications: {response.success_count} sent, {response.failure_count} failed.")
        print(f"Successfully sent push notifications: {response.success_count} sent, {response.failure_count} failed.")
    except Exception as e:
        logger.error(f"Error sending push notifications: {e}", exc_info=True)

# Helper to safely convert to ISO string

def to_iso(val):
    if hasattr(val, 'isoformat'):
        return val.isoformat()
    return val

async def trigger_alert(alert: AlertTrigger, current_user: dict = Depends(get_current_user)) -> dict:
    """Trigger a new alert"""
    logger.debug(f"trigger_alert called by user: {current_user}")
    if current_user['role'] != 'emergency_service':
        logger.warning(f"Permission denied for user: {current_user}")
        return error_response("Permission denied", 403)

    try:
        alert_id = str(uuid4())
        logger.info(f"Creating alert with id: {alert_id} and data: {alert}")
        query = """
        INSERT INTO alerts 
        (id, trigger_source, type, message, location_lat, location_lon, radius_km, created_at, triggered_by)
        VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), $8)
        RETURNING id, created_at
        """
        logger.debug(f"Executing alert insert query: {query} with params: {(alert_id, alert.trigger_source, alert.broadcast_type, alert.message, alert.location_lat, alert.location_lon, alert.radius_km, current_user['id'])}")
        result = await execute_query(
            query,
            (alert_id, alert.trigger_source, alert.type, alert.message, alert.location_lat, alert.location_lon, alert.radius_km, current_user['id']),
            commit=True,
            fetch_one=True
        )
        logger.debug(f"Alert inserted with result: {result}")

        # After saving the alert and before returning:
        alert_data = {
            "alert_id": result[0],
            "created_at": to_iso(result[1]),
            "type": alert.type,
            "message": alert.message,
            "location_lat": alert.location_lat,
            "location_lon": alert.location_lon,
            "radius_km": alert.radius_km,
            "broadcast_type": alert.broadcast_type,
            "triggered_by": current_user['id']
        }
        logger.debug(f"Prepared alert_data for broadcast: {alert_data}")
        # Determine recipients
        recipients = []
        logger.debug(f"Alert broadcast type: {alert.broadcast_type}")
        if alert.broadcast_type == "broadcast_all":
            logger.info(f"Broadcasting alert to all connected WebSocket clients: broadcast_type: {alert.broadcast_type}")
            recipients = list(connected_alert_clients.keys())
            # Also send push/SMS/email to all users
            await send_push_sms_email_to_all(alert_data)
        else:
            # Only send to clients within radius
            logger.info(f"Broadcasting alert to clients within radius: broadcast_type: {alert.broadcast_type}")
            for ws, info in list(connected_alert_clients.items()):
                loc = info.get("location")
                logger.debug(f"Checking client {ws} with location {loc}")
                if loc and None not in loc:
                    try:
                        dist = haversine(alert.location_lat, alert.location_lon, float(loc[0]), float(loc[1]))
                        logger.debug(f"Distance to client: {dist} km (radius: {alert.radius_km} km)")
                        if dist <= alert.radius_km:
                            recipients.append(ws)
                            logger.debug(f"Client {ws} is within radius and will receive alert")
                    except Exception as e:
                        logger.warning(f"Error calculating distance for client {ws}: {e}")
                        continue
        # Broadcast
        logger.info(f"Broadcasting alert to {len(recipients)} WebSocket clients")
        for ws in recipients:
            try:
                logger.debug(f"Sending alert to WebSocket client: {ws}")
                await ws.send_text(json.dumps({"event": "alert_triggered", "data": alert_data}))
            except Exception as e:
                logger.warning(f"WebSocket send failed for client {ws}: {e}")
                try:
                    connected_alert_clients.pop(ws, None)
                    logger.info(f"Removed disconnected WebSocket client: {ws}")
                except Exception as ex:
                    logger.error(f"Error removing WebSocket client {ws}: {ex}")

        logger.info(f"Alert {alert_id} triggered and notifications sent")
        return success_response({
            "alert_id": result[0],
            "created_at": to_iso(result[1])
        }, "Alert triggered successfully")
    except Exception as e:
        logger.error(f"Error triggering alert: {e}", exc_info=True)
        return error_response(str(e), 500)

async def resolve_alert(alert_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    """Resolve an alert"""
    logger.debug(f"resolve_alert called by user: {current_user} for alert_id: {alert_id}")
    if current_user['role'] != 'emergency_service':
        logger.warning(f"Permission denied for user: {current_user}")
        return error_response("Permission denied", 403)

    try:
        query = """
        UPDATE alerts 
        SET status = 'RESOLVED', 
        cooldown_until = NOW() + INTERVAL '1 hour'
        WHERE id = $1
        RETURNING id
        """
        logger.debug(f"Executing alert resolve query: {query} with alert_id: {alert_id}")
        result = await execute_query(query, (alert_id,), commit=True, fetch_one=True)
        logger.debug(f"Alert resolve query result: {result}")
        if not result:
            logger.warning(f"Alert not found: {alert_id}")
            return error_response("Alert not found", 404)
        
        logger.info(f"Alert resolved: {alert_id}")
        return success_response({"alert_id": result[0]}, "Alert resolved successfully")
    except Exception as e:
        logger.error(f"Error resolving alert: {e}", exc_info=True)
        return error_response(str(e), 500)

async def get_all_active_alerts() -> dict:
    """Get active alerts"""
    logger.debug("get_alerts called to fetch active alerts")
    try:
        query = """
        SELECT * FROM alerts 
        WHERE status = 'ACTIVE'
        ORDER BY created_at DESC
        """
        logger.debug(f"Executing get_alerts query: {query}")
        results = await execute_query(query)
        logger.debug(f"Fetched alerts: {results}")
        alerts = [
            serialize_row(r)
            for r in results
        ]
        logger.info(f"Returning {len(alerts)} active alerts")
        return success_response(alerts, "Alerts retrieved successfully")
    except Exception as e:
        logger.error(f"Error getting alerts: {e}", exc_info=True)
        return error_response(str(e), 500)

async def get_all_alerts(filters: dict = None) -> dict:
    """
    Get all alerts with optional filters (status) and pagination.
    Filters:
        - status: filter by alert status (e.g., 'ACTIVE', 'RESOLVED')
        - search: filter by type or message (case-insensitive, partial match)
        - page: page number (default 1)
        - page_size: number of items per page (default 10)
    """
    logger = logging.getLogger("alerts.manager")
    logger.info(f"Retrieving alerts with filters: {filters}")
    try:
        query = """
            SELECT * FROM alerts
        """
        count_query = "SELECT COUNT(*) FROM alerts"
        params = []
        conditions = []
        param_index = 1

        if filters:
            if filters.get('status'):
                conditions.append(f"status = ${param_index}")
                params.append(filters['status'])
                param_index += 1
            if filters.get('search'):
                conditions.append(f"(type ILIKE ${param_index} OR message ILIKE ${param_index})")
                params.append(f"%{filters['search']}%")
                param_index += 1

        if conditions:
            where_clause = ' WHERE ' + ' AND '.join(conditions)
            query += where_clause
            count_query += where_clause

        # Pagination
        page = int(filters.get('page', 1)) if filters and filters.get('page') else 1
        page_size = int(filters.get('page_size', 10)) if filters and filters.get('page_size') else 10
        offset = (page - 1) * page_size
        query += f" ORDER BY created_at DESC LIMIT {page_size} OFFSET {offset}"

        logger.debug(f"Executing query: {query} with params: {params}")
        results = await execute_query(query, tuple(params))
        total_count_result = await execute_query(count_query, tuple(params))
        total_count = total_count_result[0][0] if total_count_result else 0

        alerts = [
            serialize_row(r)
            for r in results
        ]

        base_url = '/api/alerts/'
        next_page = None
        prev_page = None
        if (page * page_size) < total_count:
            next_page = f"{base_url}?page={page + 1}&page_size={page_size}"
            if filters and filters.get('status'):
                next_page += f"&status={filters['status']}"
            if filters and filters.get('search'):
                next_page += f"&search={filters['search']}"
        if page > 1:
            prev_page = f"{base_url}?page={page - 1}&page_size={page_size}"
            if filters and filters.get('status'):
                prev_page += f"&status={filters['status']}"
            if filters and filters.get('search'):
                prev_page += f"&search={filters['search']}"

        logger.info(f"Retrieved {len(alerts)} alerts (total: {total_count})")
        return success_response({
            "alerts": alerts,
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "next_page": next_page,
            "prev_page": prev_page
        }, "Alerts retrieved successfully")
    except Exception as e:
        logger.error(f"Error retrieving alerts: {e}", exc_info=True)
        return error_response(str(e), 500)

async def get_alert_by_id(alert_id: str):
    """
    Retrieve a single alert by its ID.
    """
    from modules.shared.db import execute_query
    from modules.shared.response import success_response, error_response

    query = """
        SELECT a.id, a.trigger_source, a.type, a.message, a.location_lat, a.location_lon, a.radius_km, a.status, a.created_at, a.cooldown_until,
               u.username AS triggered_by_username
        FROM alerts a
        LEFT JOIN users u ON a.triggered_by = u.id
        WHERE a.id = $1
    """
    try:
        result = await execute_query(query, (alert_id,))
        if not result:
            return error_response("Alert not found", 404)
        r = result[0]
        alert = serialize_row(r)
        return success_response(alert, "Alert retrieved successfully")
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error retrieving alert by id: {e}", exc_info=True)
        return error_response(str(e), 500)



