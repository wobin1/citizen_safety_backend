import logging
from uuid import uuid4
from fastapi import Depends, UploadFile
from .models import IncidentSubmit, IncidentValidate
from .utils import check_profanity, check_duplicate, notify_emergency_services, notify_citizen
from modules.emergency.utils import upload_optional_media
from modules.shared.db import execute_query
from modules.shared.response import success_response, error_response
from modules.auth.manager import get_current_user
from typing import Optional
from datetime import datetime
from modules.notifications.manager import notify_broadcast

logger = logging.getLogger("incidents.manager")

def serialize_row(row):
            d = dict(row)
            for k, v in d.items():
                if isinstance(v, datetime):
                    d[k] = v.isoformat()
            return d

async def submit_incident(incident: IncidentSubmit, current_user: dict = Depends(get_current_user)) -> dict:
    """Submit a new incident report"""
    logger.info(f"User {current_user['id']} is submitting an incident: {incident}")
    try:
        if check_profanity(incident.description):
            logger.warning("Profanity detected in incident description")
            return error_response("Incident description contains inappropriate content", 400)

        incident_id = str(uuid4())
        logger.debug(f"Generated incident_id: {incident_id}")

        is_duplicate = await check_duplicate(current_user['id'], incident.type, incident.description, datetime.now())
        logger.debug(f"Duplicate check result: {is_duplicate}")
        if is_duplicate:
            logger.warning("Duplicate incident detected")
            return error_response("Duplicate incident detected", 400)

        query = """
        INSERT INTO incidents 
        (id, user_id, type, description, location_lat, location_lon, image_url, voice_note_url, video_url, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
        RETURNING id, created_at
        """
        logger.debug(f"Executing query: {query} with params: {(incident_id, current_user['id'], incident.type, incident.description, incident.location_lat, incident.location_lon, None, None, None)}")
        result = await execute_query(
            query,
            (incident_id, current_user['id'], incident.type, incident.description, incident.location_lat, incident.location_lon, None, None, None),
            commit=True,
            fetch_one=True
        )

        logger.info(f"Incident {incident_id} inserted, notifying emergency services")
        notify_emergency_services({
            'id': incident_id,
            'type': incident.type,
            'location': f"{incident.location_lat},{incident.location_lon}"
        })

        await notify_broadcast("incident.reported", {
            "id": incident_id,
            "type": incident.type,
            "location_lat": incident.location_lat,
            "location_lon": incident.location_lon,
        })

        logger.info(f"Incident {incident_id} submitted successfully")
        return success_response({
            "incident_id": result[0],
            "created_at": result[1].isoformat()
        }, "Incident submitted successfully")
    except Exception as e:
        logger.exception("Error submitting incident")
        return error_response(str(e), 500)


async def submit_incident_with_files(
    type: str,
    description: str,
    location_lat: float,
    location_lon: float,
    image: UploadFile | None,
    voice_note: UploadFile | None,
    video: UploadFile | None,
    current_user: dict,
) -> dict:
    """Submit incident with optional uploaded media, mirroring emergency submit behavior."""
    logger.info("User %s is submitting an incident with files", current_user["id"])
    try:
        if check_profanity(description):
            return error_response("Incident description contains inappropriate content", 400)

        incident_id = str(uuid4())
        is_duplicate = await check_duplicate(current_user['id'], type, description, datetime.now())
        if is_duplicate:
            return error_response("Duplicate incident detected", 400)

        # Upload media in parallel
        from asyncio import gather
        folder = f"incidents/{incident_id}"
        image_url, voice_note_url, video_url = await gather(
            upload_optional_media(image, folder),
            upload_optional_media(voice_note, folder),
            upload_optional_media(video, folder),
        )

        query = """
        INSERT INTO incidents 
        (id, user_id, type, description, location_lat, location_lon, image_url, voice_note_url, video_url, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
        RETURNING id, created_at
        """
        params = (
            incident_id,
            current_user['id'],
            type,
            description,
            location_lat,
            location_lon,
            image_url,
            voice_note_url,
            video_url,
        )
        result = await execute_query(query, params, commit=True, fetch_one=True)

        notify_emergency_services({
            'id': incident_id,
            'type': type,
            'location': f"{location_lat},{location_lon}",
        })

        return success_response({
            "incident_id": result[0],
            "created_at": result[1].isoformat()
        }, "Incident submitted successfully")
    except Exception as e:
        logger.exception("Error submitting incident with files")
        return error_response(str(e), 500)

async def validate_incident(incident_id: str, validation: IncidentValidate, current_user: dict = Depends(get_current_user)) -> dict:
    """Validate or reject an incident"""
    logger.info(f"User {current_user['id']} is validating incident {incident_id} with status {validation.status}")
    if current_user['role'] not in ['emergency_service', 'admin']:
        logger.warning(f"Unauthorized validation attempt by user {current_user['id']}")
        return error_response("Unauthorized", 403)

    try:
        query = """
        UPDATE incidents 
        SET status = $1, 
        validated_at = $2,
        rejection_reason = $3 
        WHERE id = $4
        RETURNING id
        """
        params = (
            validation.status,
            datetime.now() if validation.status in ['VALIDATED', 'ACTION_TAKEN'] else None,
            validation.rejection_reason,
            incident_id
        )
        logger.debug(f"Executing query: {query} with params: {params}")
        result = await execute_query(query, params, commit=True, fetch_one=True)
        if not result:
            logger.warning(f"Incident {incident_id} not found for validation")
            return error_response("Incident not found", 404)

        if validation.status == 'REJECTED':
            logger.info(f"Incident {incident_id} rejected, notifying citizen")
            notify_citizen(incident_id, validation.rejection_reason)
        logger.info(f"Incident {incident_id} validated successfully")
        await notify_broadcast("incident.updated", {"id": result[0], "status": validation.status})
        return success_response({"incident_id": result[0]}, "Incident validated successfully")
    except Exception as e:
        logger.exception("Error validating incident")
        return error_response(str(e), 500)

async def get_incidents(filters: Optional[dict] = None, current_user: dict = Depends(get_current_user)) -> dict:
    """Get incidents with optional filters, search, and pagination"""
    logger.info(f"User {current_user['id']} is retrieving incidents with filters: {filters}")
    try:
        query = "SELECT * FROM incidents"
        count_query = "SELECT COUNT(*) FROM incidents"
        params = []
        conditions = []
        param_index = 1
        # Filtering
        if filters:
            if filters.get('status'):
                conditions.append(f"status = ${param_index}")
                params.append(filters['status'])
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
        from datetime import datetime

        incidents = [
            serialize_row(r)
            for r in results
        ]
        logger.info(f"Retrieved {len(incidents)} incidents (total: {total_count})")
        base_url = '/api/incidents/'
        next_page = None
        prev_page = None
        if (page * page_size) < total_count:
            next_page = f"{base_url}?page={page + 1}&page_size={page_size}"
            if filters.get('status'):
                next_page += f"&status={filters['status']}"
            if filters.get('search'):
                next_page += f"&search={filters['search']}"
        if page > 1:
            prev_page = f"{base_url}?page={page - 1}&page_size={page_size}"
            if filters.get('status'):
                prev_page += f"&status={filters['status']}"
            if filters.get('search'):
                prev_page += f"&search={filters['search']}"
        logger.info(f"Retrieved {len(incidents)} incidents (total: {total_count})")
        return success_response({
            "incidents": incidents,
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "next_page": next_page,
            "prev_page": prev_page
        }, "Incidents retrieved successfully")

    except Exception as e:
        logger.exception("Error retrieving incidents")
        return error_response(str(e), 500)

async def get_incident(filters: dict, current_user: dict = Depends(get_current_user)) -> dict:
    """Get a single incident by ID"""
    incident_id = filters.get("id")
    logger.info(f"User {current_user['id']} is retrieving incident {incident_id}")
    try:
        # Validate incident_id is a valid UUID
        from uuid import UUID
        try:
            UUID(str(incident_id))
        except ValueError:
            logger.warning(f"Invalid incident_id format: {incident_id}")
            return error_response("Invalid incident ID format", 400)

        # Join with users table to get the user name
        query = """
            SELECT i.*, u.username as user_name
            FROM incidents i
            JOIN users u ON i.user_id = u.id
            WHERE i.id = $1
        """
        result = await execute_query(query, (incident_id,), fetch_one=True)
        if not result:
            logger.warning(f"Incident {incident_id} not found")
            return error_response("Incident not found", 404)
        # result is a single row, not iterable
        incident = serialize_row(result)

        logger.info(f"Incident {incident_id} retrieved successfully")
        return success_response(incident, "Incident retrieved successfully")
    except Exception as e:
        logger.exception("Error retrieving incident")
        return error_response(str(e), 500)

async def reject_incident(incident_id: str, rejection_reason: str, current_user: dict) -> dict:
    """
    Reject an incident by ID with a given reason.
    Only emergency_service or admin users should be allowed to reject.
    """
    logger.info(f"User {current_user['id']} is attempting to reject incident {incident_id} for reason: {rejection_reason}")
    try:
        # Check user role
        if current_user.get("role") not in ("emergency_service", "admin"):
            logger.warning(f"User {current_user['id']} does not have permission to reject incidents")
            return error_response("Permission denied", 403)

        # Validate incident_id is a valid UUID
        from uuid import UUID
        try:
            UUID(incident_id)
        except ValueError:
            logger.warning(f"Invalid incident_id format: {incident_id}")
            return error_response("Invalid incident ID format", 400)

        # Check if incident exists and is pending
        query = "SELECT status FROM incidents WHERE id = $1"
        result = await execute_query(query, (incident_id,), fetch_one=True)
        if not result:
            logger.warning(f"Incident {incident_id} not found")
            return error_response("Incident not found", 404)
        if result[0] != "PENDING":
            logger.warning(f"Incident {incident_id} is not pending and cannot be rejected")
            return error_response("Only pending incidents can be rejected", 400)

        # Update incident status to REJECTED and set rejection_reason
        update_query = """
            UPDATE incidents
            SET status = 'REJECTED', rejection_reason = $2, validated_at = NOW()
            WHERE id = $1
            RETURNING id, status, rejection_reason, validated_at
        """
        update_result = await execute_query(update_query, (incident_id, rejection_reason), commit=True, fetch_one=True)
        if not update_result:
            logger.error(f"Failed to update incident {incident_id} to REJECTED")
            return error_response("Failed to reject incident", 500)

        logger.info(f"Incident {incident_id} rejected successfully")
        # Optionally notify the citizen who reported the incident
        try:
            # Get user_id for notification
            user_query = "SELECT user_id FROM incidents WHERE id = $1"
            user_result = await execute_query(user_query, (incident_id,), fetch_one=True)
            if user_result:
                await notify_citizen(user_result[0], f"Your incident report was rejected: {rejection_reason}")
        except Exception as notify_exc:
            logger.warning(f"Failed to notify citizen for incident {incident_id}: {notify_exc}")

        return success_response({
            "id": update_result[0],
            "status": update_result[1],
            "rejection_reason": update_result[2],
            "validated_at": update_result[3].isoformat() if update_result[3] else None
        }, "Incident rejected successfully")
    except Exception as e:
        logger.exception("Error rejecting incident")
        return error_response(str(e), 500)

async def get_incident_stats(current_user: dict) -> dict:
    """Return stats: total pending, rejected, validated, and 5 latest pending reports"""
    try:
        # Get counts
        count_query = """
            SELECT status, COUNT(*) FROM incidents
            WHERE status IN ('PENDING', 'REJECTED', 'VALIDATED')
            GROUP BY status
        """
        count_results = await execute_query(count_query)
        stats = {"PENDING": 0, "REJECTED": 0, "VALIDATED": 0}
        for row in count_results:
            stats[row[0]] = row[1]
        # Get 5 latest pending
        latest_query = """
            SELECT id, user_id, type, description, location_lat, location_lon, status, created_at
            FROM incidents
            WHERE status = 'PENDING'
            ORDER BY created_at DESC
            LIMIT 5
        """
        latest_results = await execute_query(latest_query)
        latest_pending = [
            {
                "id": r[0],
                "user_id": r[1],
                "type": r[2],
                "description": r[3],
                "location_lat": r[4],
                "location_lon": r[5],
                "status": r[6],
                "created_at": r[7].isoformat() if r[7] else None
            }
            for r in latest_results
        ]
        return success_response({
            "pending": stats["PENDING"],
            "rejected": stats["REJECTED"],
            "validated": stats["VALIDATED"],
            "latest_pending": latest_pending
        }, "Incident stats retrieved successfully")
    except Exception as e:
        logger.exception("Error retrieving incident stats")
        return error_response(str(e), 500)
