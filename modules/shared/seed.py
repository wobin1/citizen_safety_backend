import uuid
from .db import execute_query
from passlib.context import CryptContext
import logging

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def is_table_empty(table_name):
    """Check if a table is empty."""
    result = await execute_query(
        f"SELECT COUNT(*) as count FROM {table_name}",
        (),
        fetch_one=True
    )
    return result and result["count"] == 0

async def seed_data():
    """Seed initial data into the database if tables are empty"""
    try:
        logger.info("Starting database seeding process.")

        # --- Seed 5 users (1 admin, 2 emergency_service, 2 citizens) ---
        if not await is_table_empty("users"):
            logger.info("Users table is not empty. Skipping user seeding.")
            return

        users = [
            ("admin", "admin123", "admin"),
            ("responder1", "responder123", "emergency_service"),
            ("responder2", "responder456", "emergency_service"),
            ("citizen1", "citizen123", "citizen"),
            ("citizen2", "citizen456", "citizen"),
        ]
        user_ids = {}
        for username, password, role in users:
            temp_id = str(uuid.uuid4())
            password_hash = pwd_context.hash(password)
            logger.info(f"Attempting to seed user '{username}' with ID: {temp_id}")
            await execute_query(
                """
                INSERT INTO users (id, username, password_hash, role, created_at)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (username) DO NOTHING
                """,
                (temp_id, username, password_hash, role),
                commit=True
            )
            # Fetch the actual user ID (newly inserted or existing)
            user_record = await execute_query(
                """
                SELECT id FROM users WHERE username = $1
                """,
                (username,),
                fetch_one=True
            )
            if not user_record:
                raise RuntimeError(f"Could not find user '{username}' after seeding attempt.")
            user_ids[username] = str(user_record['id'])
            logger.info(f"User '{username}' seeded with ID: {user_ids[username]}")

        # --- Seed 5 incidents ---
        if not await is_table_empty("incidents"):
            logger.info("Incidents table is not empty. Skipping incident seeding.")
            return

        incidents = [
            (
                uuid.UUID(user_ids["citizen1"]), "theft", "Stolen bicycle near park",
                "PENDING", 40.7128, -74.0060,  # New York
                "https://images.unsplash.com/photo-1600585154340-be6161a56a0c",
                "https://freesound.org/data/previews/614/614168_14136021-lq.mp3",
                "https://www.pexels.com/video/traffic-on-the-road-3010716/"
            ),
            (
                uuid.UUID(user_ids["citizen1"]), "assault", "Assault reported in alley",
                "VALIDATED", 34.0522, -118.2437,  # Los Angeles
                "https://images.unsplash.com/photo-1595675021516-8444b946b4d4",
                "https://freesound.org/data/previews/587/587216_4333520-lq.mp3",
                "https://www.pexels.com/video/city-street-scene-3046648/"
            ),
            (
                uuid.UUID(user_ids["citizen2"]), "fire", "Small fire in apartment",
                "ACTION_TAKEN", 51.5074, -0.1278,  # London
                "https://images.unsplash.com/photo-1532680678473-a16f2c6e5735",
                "https://freesound.org/data/previews/614/614169_5674468-lq.mp3",
                "https://www.pexels.com/video/fire-burning-3010717/"
            ),
            (
                uuid.UUID(user_ids["citizen2"]), "medical", "Elderly person needs help",
                "PENDING", 48.8566, 2.3522,  # Paris
                "https://images.unsplash.com/photo-1576091160550-2173dba999ef",
                "https://freesound.org/data/previews/587/587217_4333520-lq.mp3",
                "https://www.pexels.com/video/medical-emergency-scene-3046648/"
            ),
            (
                uuid.UUID(user_ids["citizen1"]), "theft", "Car break-in reported",
                "REJECTED", 35.6762, 139.6503,  # Tokyo
                "https://images.unsplash.com/photo-1593642532973-d31b97d0e6b3",
                "https://freesound.org/data/previews/614/614170_14136021-lq.mp3",
                "https://www.pexels.com/video/car-driving-3010715/"
            ),
        ]
        for i, (user_id, type_, desc, status, lat, lon, img, voice, video) in enumerate(incidents, 1):
            incident_id = str(uuid.uuid4())
            logger.info(f"Attempting to seed incident {i} with ID: {incident_id}")
            await execute_query(
                """
                INSERT INTO incidents (
                    id, user_id, type, description, status, created_at,
                    image_url, voice_note_url, video_url, location_lat, location_lon, rejection_reason
                )
                VALUES ($1, $2, $3, $4, $5, NOW(), $6, $7, $8, $9, $10, $11)
                ON CONFLICT (id) DO NOTHING
                """,
                (incident_id, user_id, type_, desc, status, img, voice, video, lat, lon, "Invalid evidence" if status == "REJECTED" else None),
                commit=True
            )
            logger.info(f"Incident {i} seeded (or already existed).")

        # --- Seed 5 alerts ---
        if not await is_table_empty("alerts"):
            logger.info("Alerts table is not empty. Skipping alert seeding.")
            return

        alerts = [
            (
                "emergency_service", "active shooter", "Active shooter reported downtown",
                "broadcast_all", 40.7128, -74.0060, 5.0, "ACTIVE"
            ),
            (
                "sensor", "natural disaster", "Flood warning issued",
                "broadcast_neighborhood", 34.0522, -118.2437, 2.0, "ACTIVE"
            ),
            (
                "manual", "missing person", "Missing child in park",
                "broadcast_neighborhood", 51.5074, -0.1278, 1.5, "COOLDOWN"
            ),
            (
                "emergency_service", "natural disaster", "Earthquake alert",
                "broadcast_all", 35.6762, 139.6503, 10.0, "RESOLVED"
            ),
            (
                "manual", "missing person", "Missing elderly person",
                "broadcast_neighborhood", 48.8566, 2.3522, 3.0, "ACTIVE"
            ),
        ]
        for i, (source, type_, msg, broadcast, lat, lon, radius, status) in enumerate(alerts, 1):
            alert_id = str(uuid.uuid4())
            logger.info(f"Attempting to seed alert {i} with ID: {alert_id}")
            await execute_query(
                """
                INSERT INTO alerts (
                    id, trigger_source, type, message, broadcast_type,
                    location_lat, location_lon, radius_km, status, created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
                ON CONFLICT (id) DO NOTHING
                """,
                (alert_id, source, type_, msg, broadcast, lat, lon, radius, status),
                commit=True
            )
            logger.info(f"Alert {i} seeded (or already existed).")

        # --- Seed 5 emergencies ---
        if not await is_table_empty("emergency"):
            logger.info("Emergency table is not empty. Skipping emergency seeding.")
            return

        emergencies = [
            (
                uuid.UUID(user_ids["citizen1"]), "medical_emergency", "Person collapsed in street",
                "PENDING", 40.7128, -74.0060, "CRITICAL", uuid.UUID(user_ids["responder1"]),
                "https://images.unsplash.com/photo-1576091160550-2173dba999ef",
                "https://freesound.org/data/previews/587/587216_4333520-lq.mp3",
                "https://www.pexels.com/video/medical-emergency-scene-3046648/"
            ),
            (
                uuid.UUID(user_ids["citizen2"]), "fire_emergency", "House fire reported",
                "VALIDATED", 34.0522, -118.2437, "HIGH", uuid.UUID(user_ids["responder1"]),
                "https://images.unsplash.com/photo-1532680678473-a16f2c6e5735",
                "https://freesound.org/data/previews/614/614169_5674468-lq.mp3",
                "https://www.pexels.com/video/fire-burning-3010717/"
            ),
            (
                uuid.UUID(user_ids["citizen1"]), "crime_emergency", "Robbery in progress",
                "PENDING", 51.5074, -0.1278, "CRITICAL", uuid.UUID(user_ids["responder2"]),
                "https://images.unsplash.com/photo-1595675021516-8444b946b4d4",
                "https://freesound.org/data/previews/614/614168_14136021-lq.mp3",
                "https://www.pexels.com/video/city-street-scene-3046648/"
            ),
            (
                uuid.UUID(user_ids["citizen2"]), "disaster_emergency", "Flooding in neighborhood",
                "ACTION_TAKEN", 35.6762, 139.6503, "MEDIUM", uuid.UUID(user_ids["responder2"]),
                "https://images.unsplash.com/photo-1593642532973-d31b97d0e6b3",
                "https://freesound.org/data/previews/614/614170_14136021-lq.mp3",
                "https://www.pexels.com/video/flooded-area-3010718/"
            ),
            (
                uuid.UUID(user_ids["citizen1"]), "medical_emergency", "Heart attack reported",
                "REJECTED", 48.8566, 2.3522, "HIGH", None,
                "https://images.unsplash.com/photo-1583911860205-738d9c3198a1",
                "https://freesound.org/data/previews/587/587217_4333520-lq.mp3",
                "https://www.pexels.com/video/medical-emergency-3046649/"
            ),
        ]
        for i, (user_id, type_, desc, status, lat, lon, severity, responder_id, img, voice, video) in enumerate(emergencies, 1):
            emergency_id = str(uuid.uuid4())
            logger.info(f"Attempting to seed emergency {i} with ID: {emergency_id}")
            await execute_query(
                """
                INSERT INTO emergency (
                    id, user_id, type, description, status, created_at,
                    image_url, voice_note_url, video_url,
                    location_lat, location_lon, severity, responder_id,
                    rejection_reason
                )
                VALUES ($1, $2, $3, $4, $5, NOW(), $6, $7, $8, $9, $10, $11, $12, $13)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    emergency_id, user_id, type_, desc, status, img, voice, video,
                    lat, lon, severity, responder_id,
                    "Insufficient evidence" if status == "REJECTED" else None
                ),
                commit=True
            )
            logger.info(f"Emergency {i} seeded (or already existed).")

        logger.info("Database seeding process completed successfully.")

    except Exception as e:
        logger.exception(f"Error seeding data: {str(e)}")
        raise