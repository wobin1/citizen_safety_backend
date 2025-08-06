import logging
from uuid import uuid4, UUID
from fastapi import Depends
from datetime import datetime
from typing import Optional, Dict
from .models import EmergencySubmit, EmergencyValidate, EmergencyReject
from .utils import check_profanity, check_duplicate, notify_emergency_services, notify_citizen
from modules.shared.db import execute_query
from modules.shared.response import success_response, error_response
from modules.auth.manager import get_current_user

logger = logging.getLogger("emergency.manager")

def serialize_row(row):
    """Serialize database row, converting datetime to ISO format"""
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d

async def submit_emergency(emergency: EmergencySubmit, current_user: dict = Depends(get_current_user)) -> dict:
    """Submit a new emergency report"""
    logger.info(f"User {current_user['id']} is submitting an emergency: {emergency}")
    try:
        if check_profanity(emergency.description):
            logger.warning("Profanity detected in emergency description")
            return error_response("Emergency description contains inappropriate content", 400)

        emergency_id = str(uuid4())
        logger.debug(f"Generated emergency_id: {emergency_id}")

        is_duplicate = await check_duplicate(current_user['id'], emergency.type, emergency.description, datetime.now())
        logger.debug(f"Duplicate check result: {is_duplicate}")
        if is_duplicate:
            logger.warning("Duplicate emergency detected")
            return error_response("Duplicate emergency detected", 400)

        query = """
        INSERT INTO emergency 
        (id, user_id, type, description, location_lat, location_lon, severity, 
         image_url, voice_note_url, video_url, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())
        RETURNING id, created_at
        """
        params = (
            emergency_id,
            current_user['id'],
            emergency.type,
            emergency.description,
            emergency.location_lat,
            emergency.location_lon,
            emergency.severity,
            emergency.image_url,
            emergency.voice_note_url,
            emergency.video_url,
        )
        logger.debug(f"Executing query: {query} with params: {params}")
        result = await execute_query(query, params, commit=True, fetch_one=True)

        logger.info(f"Emergency {emergency_id} inserted, notifying emergency services")
        notify_emergency_services({
            'id': emergency_id,
            'type': emergency.type,
            'location': f"{emergency.location_lat},{emergency.location_lon}",
            'severity': emergency.severity
        })

        logger.info(f"Emergency {emergency_id} submitted successfully")
        return success_response({
            "emergency_id": result[0],
            "created_at": result[1].isoformat()
        }, "Emergency submitted successfully")
    except Exception as e:
        logger.exception("Error submitting emergency")
        return error_response(str(e), 500)

async def validate_emergency(emergency_id: str, validation: EmergencyValidate, current_user: dict = Depends(get_current_user)) -> dict:
    """Validate or reject an emergency"""
    logger.info(f"User {current_user['id']} is validating emergency {emergency_id} with status {validation.status}")
    if current_user['role'] not in ['emergency_service', 'admin']:
        logger.warning(f"Unauthorized validation attempt by user {current_user['id']}")
        return error_response("Unauthorized", 403)

    try:
        query = """
        UPDATE emergency 
        SET status = $1, 
            rejection_reason = $2,
            updated_at = NOW(),
            responder_id = $3
        WHERE id = $4
        RETURNING id
        """
        params = (
            validation.status,
            validation.rejection_reason,
            current_user['id'],
            emergency_id
        )
        logger.debug(f"Executing query: {query} with params: {params}")
        result = await execute_query(query, params, commit=True, fetch_one=True)
        if not result:
            logger.warning(f"Emergency {emergency_id} not found for validation")
            return error_response("Emergency not found", 404)

        if validation.status == 'CANCELLED':
            logger.info(f"Emergency {emergency_id} cancelled, notifying citizen")
            notify_citizen(emergency_id, validation.rejection_reason or "Emergency cancelled")
        logger.info(f"Emergency {emergency_id} validated successfully")
        return success_response({"emergency_id": result[0]}, "Emergency validated successfully")
    except Exception as e:
        logger.exception("Error validating emergency")
        return error_response(str(e), 500)

async def mark_action_taken(emergency_id: str, current_user: dict) -> dict:
    """
    Mark an emergency as 'VALIDATED' (action taken).
    Only emergency_service or admin can perform this action.
    """
    logger.info(f"User {current_user['id']} is marking emergency {emergency_id} as action taken (VALIDATED)")
    if current_user['role'] not in ['emergency_service', 'admin']:
        logger.warning(f"Unauthorized action taken attempt by user {current_user['id']}")
        return error_response("Unauthorized", 403)

    try:
        query = """
        UPDATE emergency
        SET status = 'ACTION_TAKEN',
            updated_at = NOW(),
            responder_id = $1
        WHERE id = $2
        RETURNING id
        """
        params = (
            current_user['id'],
            emergency_id
        )
        logger.debug(f"Executing query: {query} with params: {params}")
        result = await execute_query(query, params, commit=True, fetch_one=True)
        if not result:
            logger.warning(f"Emergency {emergency_id} not found for action taken")
            return error_response("Emergency not found", 404)

        logger.info(f"Emergency {emergency_id} marked as action taken (VALIDATED) successfully")
        return success_response({"emergency_id": result[0]}, "Emergency marked as action taken (VALIDATED) successfully")
    except Exception as e:
        logger.exception("Error marking emergency as action taken")
        return error_response(str(e), 500)


async def get_emergencies(filters: Optional[dict] = None, current_user: dict = Depends(get_current_user)) -> dict:
    """Get emergencies with optional filters, search, and pagination"""
    logger.info(f"User {current_user['id']} is retrieving emergencies with filters: {filters}")
    try:
        query = "SELECT * FROM emergency"
        count_query = "SELECT COUNT(*) FROM emergency"
        params = []
        conditions = []
        param_index = 1

        # Filtering
        if filters:
            if filters.get('status'):
                conditions.append(f"status = ${param_index}")
                params.append(filters['status'])
                param_index += 1
            if filters.get('severity'):
                conditions.append(f"severity = ${param_index}")
                params.append(filters['severity'])
                param_index += 1
            if filters.get('search'):
                conditions.append(f"(type ILIKE ${param_index} OR description ILIKE ${param_index})")
                params.append(f"%{filters['search']}%")
                param_index += 1

        if conditions:
            where_clause = ' WHERE ' + ' AND '.join(conditions)
            query += where_clause
            count_query += where_clause

        # Pagination
        page = int(filters.get('page', 1))
        page_size = int(filters.get('page_size', 10))
        offset = (page - 1) * page_size
        query += f" ORDER BY created_at DESC LIMIT {page_size} OFFSET {offset}"

        logger.debug(f"Executing query: {query} with params: {params}")
        results = await execute_query(query, tuple(params))

        # Get total count for pagination
        total_count_result = await execute_query(count_query, tuple(params))
        total_count = total_count_result[0][0] if total_count_result else 0

        emergencies = [serialize_row(r) for r in results]
        logger.info(f"Retrieved {len(emergencies)} emergencies (total: {total_count})")

        base_url = '/api/emergencies/'
        next_page = None
        prev_page = None
        if (page * page_size) < total_count:
            next_page = f"{base_url}?page={page + 1}&page_size={page_size}"
            if filters.get('status'):
                next_page += f"&status={filters['status']}"
            if filters.get('severity'):
                next_page += f"&severity={filters['severity']}"
            if filters.get('search'):
                next_page += f"&search={filters['search']}"
        if page > 1:
            prev_page = f"{base_url}?page={page - 1}&page_size={page_size}"
            if filters.get('status'):
                prev_page += f"&status={filters['status']}"
            if filters.get('severity'):
                prev_page += f"&severity={filters['severity']}"
            if filters.get('search'):
                prev_page += f"&search={filters['search']}"

        logger.info(f"Retrieved {len(emergencies)} emergencies (total: {total_count})")
        return success_response({
            "emergencies": emergencies,
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "next_page": next_page,
            "prev_page": prev_page
        }, "Emergencies retrieved successfully")

    except Exception as e:
        logger.exception("Error retrieving emergencies")
        return error_response(str(e), 500)

async def get_emergency(filters: dict, current_user: dict = Depends(get_current_user)) -> dict:
    """Get a single emergency by ID"""
    emergency_id = filters.get("id")
    logger.info(f"User {current_user['id']} is retrieving emergency {emergency_id}")
    try:
        # Validate emergency_id is a valid UUID
        try:
            UUID(str(emergency_id))
        except ValueError:
            logger.warning(f"Invalid emergency_id format: {emergency_id}")
            return error_response("Invalid emergency ID format", 400)

        # Join with users table to get the user name and responder name
        query = """
            SELECT e.*, u.username as user_name, r.username as responder_name
            FROM emergency e
            JOIN users u ON e.user_id = u.id
            LEFT JOIN users r ON e.responder_id = r.id
            WHERE e.id = $1
        """
        result = await execute_query(query, (emergency_id,), fetch_one=True)
        if not result:
            logger.warning(f"Emergency {emergency_id} not found")
            return error_response("Emergency not found", 404)

        emergency = serialize_row(result)
        logger.info(f"Emergency {emergency_id} retrieved successfully")
        return success_response(emergency, "Emergency retrieved successfully")
    except Exception as e:
        logger.exception("Error retrieving emergency")
        return error_response(str(e), 500)

async def reject_emergency(emergency_id: str, rejection_reason: str, current_user: dict) -> dict:
    """Reject an emergency by ID with a given reason"""
    logger.info(f"User {current_user['id']} is attempting to reject emergency {emergency_id} for reason: {rejection_reason}")
    try:
        if current_user.get("role") not in ("emergency_service", "admin"):
            logger.warning(f"User {current_user['id']} does not have permission to reject emergencies")
            return error_response("Permission denied", 403)

        try:
            UUID(emergency_id)
        except ValueError:
            logger.warning(f"Invalid emergency_id format: {emergency_id}")
            return error_response("Invalid emergency ID format", 400)

        query = "SELECT status FROM emergency WHERE id = $1"
        result = await execute_query(query, (emergency_id,), fetch_one=True)
        if not result:
            logger.warning(f"Emergency {emergency_id} not found")
            return error_response("Emergency not found", 404)
        
        update_query = """
            UPDATE emergency
            SET status = 'REJECTED', rejection_reason = $2, updated_at = NOW()
            WHERE id = $1
            RETURNING id, status, rejection_reason
        """
        update_result = await execute_query(update_query, (emergency_id, rejection_reason), commit=True, fetch_one=True)
        if not update_result:
            logger.error(f"Failed to update emergency {emergency_id} to CANCELLED")
            return error_response("Failed to reject emergency", 500)

        logger.info(f"Emergency {emergency_id} rejected successfully")
        try:
            user_query = "SELECT user_id FROM emergency WHERE id = $1"
            user_result = await execute_query(user_query, (emergency_id,), fetch_one=True)
            if user_result:
                await notify_citizen(user_result[0], f"Your emergency report was rejected: {rejection_reason}")
        except Exception as notify_exc:
            logger.warning(f"Failed to notify citizen for emergency {emergency_id}: {notify_exc}")

        return success_response({
            "id": update_result[0],
            "status": update_result[1],
            "rejection_reason": update_result[2],
        }, "Emergency rejected successfully")
    except Exception as e:
        logger.exception("Error rejecting emergency")
        return error_response(str(e), 500)

async def get_emergency_stats(current_user: dict) -> dict:
    """Return stats: total reported, dispatched, resolved, cancelled, and 5 latest reported emergencies"""
    try:
        count_query = """
            SELECT status, COUNT(*) FROM emergency
            WHERE status IN ('REPORTED', 'DISPATCHED', 'RESOLVED', 'CANCELLED')
            GROUP BY status
        """
        count_results = await execute_query(count_query)
        stats = {"REPORTED": 0, "DISPATCHED": 0, "RESOLVED": 0, "CANCELLED": 0}
        for row in count_results:
            stats[row[0]] = row[1]

        latest_query = """
            SELECT id, user_id, type, description, location_lat, location_lon, severity, status, created_at
            FROM emergency
            WHERE status = 'REPORTED'
            ORDER BY created_at DESC
            LIMIT 5
        """
        latest_results = await execute_query(latest_query)
        latest_reported = [
            {
                "id": r[0],
                "user_id": r[1],
                "type": r[2],
                "description": r[3],
                "location_lat": r[4],
                "location_lon": r[5],
                "severity": r[6],
                "status": r[7],
                "created_at": r[8].isoformat() if r[8] else None
            }
            for r in latest_results
        ]

        return success_response({
            "reported": stats["REPORTED"],
            "dispatched": stats["DISPATCHED"],
            "resolved": stats["RESOLVED"],
            "cancelled": stats["CANCELLED"],
            "latest_reported": latest_reported
        }, "Emergency stats retrieved successfully")
    except Exception as e:
        logger.exception("Error retrieving emergency stats")
        return error_response(str(e), 500)