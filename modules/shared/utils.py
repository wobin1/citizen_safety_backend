import logging

async def get_all_locations():
    """
    Fetches all locations from incidents, alerts, and emergency tables,
    and combines them into a single list of JSON objects for map display.
    Each object includes location_lat, location_lon, and type ("Incident", "Alert", "Emergency").
    """
    from modules.shared.db import execute_query

    logger = logging.getLogger(__name__)
    try:
        # Query for incidents
        incidents_query = """
            SELECT location_lat, location_lon
            FROM incidents
            WHERE location_lat IS NOT NULL AND location_lon IS NOT NULL
        """
        # Query for alerts
        alerts_query = """
            SELECT location_lat, location_lon
            FROM alerts
            WHERE location_lat IS NOT NULL AND location_lon IS NOT NULL
        """
        # Query for emergency
        emergency_query = """
            SELECT location_lat, location_lon
            FROM emergency
            WHERE location_lat IS NOT NULL AND location_lon IS NOT NULL
        """

        incidents = await execute_query(incidents_query)
        alerts = await execute_query(alerts_query)
        emergencies = await execute_query(emergency_query)

        locations = []

        for row in incidents:
            locations.append({
                "location_lat": float(row[0]),
                "location_lon": float(row[1]),
                "type": "Incident"
            })
        for row in alerts:
            locations.append({
                "location_lat": float(row[0]),
                "location_lon": float(row[1]),
                "type": "Alert"
            })
        for row in emergencies:
            locations.append({
                "location_lat": float(row[0]),
                "location_lon": float(row[1]),
                "type": "Emergency"
            })

        return locations
    except Exception as e:
        logger.error(f"Error fetching all locations: {e}", exc_info=True)
        raise

