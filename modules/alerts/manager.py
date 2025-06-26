import logging
from uuid import uuid4
from datetime import datetime, timedelta
from fastapi import Depends
from .models import AlertTrigger, AlertResponse
from .utils import dispatch_alert, notify_emergency_services_alert
from modules.shared.db import execute_query
from modules.shared.response import success_response, error_response
from modules.auth.manager import get_current_user

logger = logging.getLogger(__name__)

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
        (id, trigger_source, type, message, location_lat, location_lon, radius_km, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
        RETURNING id, created_at
        """
        result = await execute_query(
            query,
            (alert_id, alert.trigger_source, alert.type, alert.message, alert.location_lat, alert.location_lon, alert.radius_km),
            commit=True,
            fetch_one=True
        )
        logger.debug(f"Alert inserted with result: {result}")

        dispatch_alert({
            'id': alert_id,
            'type': alert.type,
            'radius_km': alert.radius_km
        })
        logger.info(f"Dispatched alert: {alert_id}")

        notify_emergency_services_alert({
            'id': alert_id,
            'type': alert.type
        })
        logger.info(f"Notified emergency services for alert: {alert_id}")

        return success_response({
            "alert_id": result[0],
            "created_at": result[1].isoformat()
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

async def get_alerts(current_user: dict = Depends(get_current_user)) -> dict:
    """Get active alerts"""
    logger.debug(f"get_alerts called by user: {current_user}")
    try:
        query = """
        SELECT * FROM alerts 
        WHERE status = 'ACTIVE'
        ORDER BY created_at DESC
        """
        results = await execute_query(query)
        logger.debug(f"Fetched alerts: {results}")
        alerts = [
            {
                "id": r[0],
                "trigger_source": r[1],
                "type": r[2],
                "message": r[3],
                "location_lat": r[4],
                "location_lon": r[5],
                "radius_km": r[6],
                "status": r[7],
                "created_at": r[8].isoformat(),
                "cooldown_until": r[9].isoformat() if r[9] else None
            }
            for r in results
        ]
        logger.info(f"Returning {len(alerts)} active alerts")
        return success_response(alerts, "Alerts retrieved successfully")
    except Exception as e:
        logger.error(f"Error getting alerts: {e}", exc_info=True)
        return error_response(str(e), 500)