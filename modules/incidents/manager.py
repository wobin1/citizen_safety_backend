import logging
from uuid import uuid4
from fastapi import Depends
from .models import IncidentSubmit, IncidentValidate
from .utils import check_profanity, check_duplicate, notify_emergency_services, notify_citizen
from modules.shared.db import execute_query
from modules.shared.response import success_response, error_response
from modules.auth.manager import get_current_user
from typing import Optional
from datetime import datetime

logger = logging.getLogger("incidents.manager")

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
        (id, user_id, type, description, location_lat, location_lon, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, NOW())
        RETURNING id, created_at
        """
        logger.debug(f"Executing query: {query} with params: {(incident_id, current_user['id'], incident.type, incident.description, incident.location_lat, incident.location_lon)}")
        result = await execute_query(
            query,
            (incident_id, current_user['id'], incident.type, incident.description, incident.location_lat, incident.location_lon),
            commit=True,
            fetch_one=True
        )

        logger.info(f"Incident {incident_id} inserted, notifying emergency services")
        notify_emergency_services({
            'id': incident_id,
            'type': incident.type,
            'location': f"{incident.location_lat},{incident.location_lon}"
        })

        logger.info(f"Incident {incident_id} submitted successfully")
        return success_response({
            "incident_id": result[0],
            "created_at": result[1].isoformat()
        }, "Incident submitted successfully")
    except Exception as e:
        logger.exception("Error submitting incident")
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
        return success_response({"incident_id": result[0]}, "Incident validated successfully")
    except Exception as e:
        logger.exception("Error validating incident")
        return error_response(str(e), 500)

async def get_incidents(filters: Optional[dict] = None, current_user: dict = Depends(get_current_user)) -> dict:
    """Get incidents with optional filters"""
    logger.info(f"User {current_user['id']} is retrieving incidents with filters: {filters}")
    try:
        query = "SELECT * FROM incidents"
        params = []
        if filters:
            conditions = []
            if filters.get('type'):
                conditions.append("type = $1")
                params.append(filters['type'])
            if filters.get('status'):
                conditions.append("status = $2")
                params.append(filters['status'])
            if conditions:
                query += " WHERE " + ' AND '.join(conditions)
        logger.debug(f"Executing query: {query} with params: {params}")
        results = await execute_query(query, tuple(params))
        incidents = [
            {
                "id": r[0],
                "user_id": r[1],
                "type": r[2],
                "description": r[3],
                "location_lat": r[4],
                "location_lon": r[5],
                "status": r[6],
                "created_at": r[7].isoformat(),
                "validated_at": r[8].isoformat() if r[8] else None,
                "rejection_reason": r[9]
            }
            for r in results
        ]
        logger.info(f"Retrieved {len(incidents)} incidents")
        return success_response(incidents, "Incidents retrieved successfully")
    except Exception as e:
        logger.exception("Error retrieving incidents")
        return error_response(str(e), 500)

async def get_incident(incident_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    """Get a single incident by ID"""
    logger.info(f"User {current_user['id']} is retrieving incident {incident_id}")
    try:
        # Validate incident_id is a valid UUID
        from uuid import UUID
        try:
            UUID(incident_id["id"])
        except ValueError:
            logger.warning(f"Invalid incident_id format: {incident_id["id"]}")
            return error_response("Invalid incident ID format", 400)

        query = "SELECT * FROM incidents WHERE id = $1"
        result = await execute_query(query, (incident_id["id"],), fetch_one=True)
        if not result:
            logger.warning(f"Incident {incident_id["id"]} not found")
            return error_response("Incident not found", 404)
        incident = {
            "id": result[0],
            "user_id": result[1],
            "type": result[2],
            "description": result[3],
            "location_lat": result[4],
            "location_lon": result[5],
            "status": result[6],
            "created_at": result[7].isoformat(),
            "validated_at": result[8].isoformat() if result[8] else None,
            "rejection_reason": result[9]
        }
        logger.info(f"Incident {incident_id["id"]} retrieved successfully")
        return success_response(incident, "Incident retrieved successfully")
    except Exception as e:
        logger.exception("Error retrieving incident")
        return error_response(str(e), 500)

