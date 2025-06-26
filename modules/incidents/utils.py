import re
from datetime import datetime, timedelta
from modules.shared.db import execute_query

def check_profanity(text: str) -> bool:
    """Simple profanity check using regex"""
    profanity_pattern = re.compile(r'\b(fuck|shit|ass|damn)\b', re.IGNORECASE)
    return bool(profanity_pattern.search(text))

async def check_duplicate(user_id: str, incident_type: str, description: str, created_at: datetime) -> bool:
    """Check for duplicate incidents"""
    time_window = created_at - timedelta(hours=1)
    query = """
    SELECT COUNT(*) 
    FROM incidents 
    WHERE user_id = $1 
    AND type = $2 
    AND description = $3
    AND created_at >= $4
    """
    result = await execute_query(query, (user_id, incident_type, description, time_window))
    return result[0][0] > 0

def notify_emergency_services(incident: dict):
    """Mock emergency service notification"""
    print(f"Mock: Notifying emergency services of {incident['type']} at {incident['location']}")

def notify_citizen(incident_id: str, reason: str):
    """Mock citizen notification"""
    print(f"Mock: Notifying citizen of rejected incident {incident_id}: {reason}")