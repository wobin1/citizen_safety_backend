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
            ("admin", "admin@citizensafety.com", "admin123", "admin", "fcm_token_admin_123"),
            ("responder1", "responder1@emergency.gov.ng", "responder123", "emergency_service", "fcm_token_resp1_456"),
            ("responder2", "responder2@emergency.gov.ng", "responder456", "emergency_service", "fcm_token_resp2_789"),
            ("citizen1", "citizen1@gmail.com", "citizen123", "citizen", "fcm_token_citizen1_abc"),
            ("citizen2", "citizen2@yahoo.com", "citizen456", "citizen", "fcm_token_citizen2_def"),
        ]
        user_ids = {}
        for username, email, password, role, fcm_token in users:
            temp_id = str(uuid.uuid4())
            password_hash = pwd_context.hash(password)
            logger.info(f"Attempting to seed user '{username}' with ID: {temp_id}")
            await execute_query(
                """
                INSERT INTO users (id, username, email, password_hash, role, fcm_token, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, NOW())
                ON CONFLICT (username) DO NOTHING
                """,
                (temp_id, username, email, password_hash, role, fcm_token),
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
                uuid.UUID(user_ids["citizen1"]), "theft", "Stolen bicycle near Ikeja",
                "PENDING", 6.4531, 3.4642,  # Lagos
                "https://images.unsplash.com/photo-1600585154340-be6161a56a0c",
                "https://freesound.org/data/previews/614/614168_14136021-lq.mp3",
                "https://www.pexels.com/video/traffic-on-the-road-3010716/"
            ),
            (
                uuid.UUID(user_ids["citizen1"]), "assault", "Assault reported in Lekki",
                "VALIDATED", 6.4522, 3.4242,  # Lagos
                "https://images.unsplash.com/photo-1595675021516-8444b946b4d4",
                "https://freesound.org/data/previews/587/587216_4333520-lq.mp3",
                "https://www.pexels.com/video/city-street-scene-3046648/"
            ),
            (
                uuid.UUID(user_ids["citizen2"]), "fire", "Small fire in a hotel",
                "ACTION_TAKEN", 6.4762, 3.4378,  # Lagos
                "https://images.unsplash.com/photo-1576091160550-2173dba999ef",
                "https://freesound.org/data/previews/614/614169_5674468-lq.mp3",
                "https://www.pexels.com/video/fire-burning-3010717/"
            ),
            (
                uuid.UUID(user_ids["citizen2"]), "medical", "Elderly person needs help",
                "PENDING", 6.4454, 3.4522,  # Lagos
                "https://images.unsplash.com/photo-1532680678473-a16f2c6e5735",
                "https://freesound.org/data/previews/587/587217_4333520-lq.mp3",
                "https://www.pexels.com/video/medical-emergency-scene-3046648/"
            ),
            (
                uuid.UUID(user_ids["citizen1"]), "theft", "Car break-in reported",
                "REJECTED", 6.4362, 3.4638,  # Lagos
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

        # --- Seed 5 emergency alerts ---
        if not await is_table_empty("alerts"):
            logger.info("Alerts table is not empty. Skipping alert seeding.")
        else:
            alerts = [
                (
                    "emergency_service", "active shooter", 
                    "Active shooter reported at Victoria Island shopping complex. Avoid the area.",
                    "broadcast_all", 6.4281, 3.4219, 2.0, "ACTIVE"  # Victoria Island, Lagos
                ),
                (
                    "sensor", "natural disaster",
                    "Flood warning issued for Ikoyi and surrounding areas due to heavy rainfall.",
                    "broadcast_neighborhood", 6.4474, 3.4553, 5.0, "ACTIVE"  # Ikoyi, Lagos
                ),
                (
                    "manual", "missing person",
                    "Missing child last seen near National Theatre. 8-year-old boy wearing blue shirt.",
                    "broadcast_neighborhood", 6.4698, 3.3792, 3.0, "ACTIVE"  # National Theatre area
                ),
                (
                    "emergency_service", "natural disaster",
                    "Gas leak reported in Surulere residential area. Evacuation in progress.",
                    "broadcast_neighborhood", 6.4969, 3.3603, 1.5, "RESOLVED"  # Surulere, Lagos
                ),
                (
                    "sensor", "active shooter",
                    "Security alert at University of Lagos campus has been resolved.",
                    "broadcast_all", 6.5158, 3.3896, 1.0, "RESOLVED"  # UNILAG
                ),
            ]
            
            for i, (trigger_source, alert_type, message, broadcast_type, lat, lon, radius, status) in enumerate(alerts, 1):
                alert_id = str(uuid.uuid4())
                logger.info(f"Attempting to seed alert {i} with ID: {alert_id}")
                
                # Set cooldown_until for resolved alerts
                cooldown_until = "NOW() + INTERVAL '24 hours'" if status == "RESOLVED" else None
                
                await execute_query(
                    """
                    INSERT INTO alerts (
                        id, trigger_source, type, message, broadcast_type, location_lat, location_lon, 
                        radius_km, status, created_at, cooldown_until
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), $10)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (alert_id, trigger_source, alert_type, message, broadcast_type, lat, lon, radius, status, 
                     cooldown_until if cooldown_until is None else None),
                    commit=True
                )
                
                # For resolved alerts, update cooldown_until separately
                if status == "RESOLVED":
                    await execute_query(
                        """
                        UPDATE alerts SET cooldown_until = NOW() + INTERVAL '24 hours' 
                        WHERE id = $1
                        """,
                        (alert_id,),
                        commit=True
                    )
                
                logger.info(f"Alert {i} seeded (or already existed).")

        # --- Seed 5 emergency records ---
        if not await is_table_empty("emergency"):
            logger.info("Emergency table is not empty. Skipping emergency seeding.")
        else:
            emergencies = [
                (
                    uuid.UUID(user_ids["citizen1"]), "medical_emergency",
                    "Heart attack victim needs immediate medical attention",
                    6.4531, 3.4642, "HIGH",  # Lagos
                    "https://images.unsplash.com/photo-1584432810601-6c7f27d2362b",
                    "https://freesound.org/data/previews/316/316847_5123451-lq.mp3",
                    None, "PENDING"
                ),
                (
                    uuid.UUID(user_ids["citizen2"]), "fire_emergency",
                    "Building fire spreading rapidly in residential area",
                    6.4474, 3.4553, "CRITICAL",  # Ikoyi
                    "https://images.unsplash.com/photo-1574169208507-84376144848b",
                    None,
                    "https://www.pexels.com/video/fire-emergency-3010718/",
                    "ACTION_TAKEN"
                ),
                (
                    uuid.UUID(user_ids["citizen1"]), "crime_emergency",
                    "Armed robbery in progress at bank location",
                    6.4281, 3.4219, "CRITICAL",  # Victoria Island
                    "https://images.unsplash.com/photo-1590736969955-71cc94901144",
                    "https://freesound.org/data/previews/587/587218_4333520-lq.mp3",
                    None, "VALIDATED"
                ),
                (
                    uuid.UUID(user_ids["citizen2"]), "disaster_emergency",
                    "Building collapse with people trapped inside",
                    6.4969, 3.3603, "CRITICAL",  # Surulere
                    "https://images.unsplash.com/photo-1558618666-fcd25c85cd64",
                    "https://freesound.org/data/previews/614/614171_14136021-lq.mp3",
                    "https://www.pexels.com/video/rescue-operation-3010719/",
                    "ACTION_TAKEN"
                ),
                (
                    uuid.UUID(user_ids["citizen1"]), "medical_emergency",
                    "Multiple casualties from vehicle accident",
                    6.5158, 3.3896, "HIGH",  # UNILAG area
                    "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b",
                    None, None, "PENDING"
                ),
            ]
            
            for i, (user_id, emerg_type, desc, lat, lon, severity, img, voice, video, status) in enumerate(emergencies, 1):
                emergency_id = str(uuid.uuid4())
                logger.info(f"Attempting to seed emergency {i} with ID: {emergency_id}")
                
                # Set responder for action_taken emergencies
                responder_id = uuid.UUID(user_ids["responder1"]) if status == "ACTION_TAKEN" else None
                response_time = "NOW() - INTERVAL '30 minutes'" if status == "ACTION_TAKEN" else None
                
                await execute_query(
                    """
                    INSERT INTO emergency (
                        id, user_id, type, description, location_lat, location_lon, 
                        severity, status, created_at, image_url, voice_note_url, video_url,
                        responder_id, response_time
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), $9, $10, $11, $12, $13)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (emergency_id, user_id, emerg_type, desc, lat, lon, severity, status, 
                     img, voice, video, responder_id, None),
                    commit=True
                )
                
                # Update response_time for action_taken emergencies
                if status == "ACTION_TAKEN":
                    await execute_query(
                        """
                        UPDATE emergency SET response_time = NOW() - INTERVAL '30 minutes'
                        WHERE id = $1
                        """,
                        (emergency_id,),
                        commit=True
                    )
                
                logger.info(f"Emergency {i} seeded (or already existed).")

        # --- Seed notifications ---
        if not await is_table_empty("notifications"):
            logger.info("Notifications table is not empty. Skipping notification seeding.")
        else:
            # Get some alert and emergency IDs for linking
            alert_records = await execute_query(
                "SELECT id FROM alerts LIMIT 3",
                ()
            )
            emergency_records = await execute_query(
                "SELECT id FROM emergency LIMIT 2", 
                ()
            )
            
            notifications = []
            
            # Alert notifications
            if alert_records:
                for i, alert_record in enumerate(alert_records):
                    for username in ["citizen1", "citizen2"]:
                        notifications.append((
                            uuid.UUID(user_ids[username]), alert_record["id"], None,
                            "alert", f"Emergency alert #{i+1}: Please stay safe and follow instructions.",
                            i % 2 == 0  # Alternate read/unread
                        ))
            
            # Emergency notifications  
            if emergency_records:
                for i, emergency_record in enumerate(emergency_records):
                    for username in ["responder1", "responder2"]:
                        notifications.append((
                            uuid.UUID(user_ids[username]), None, emergency_record["id"],
                            "report", f"Emergency report #{i+1}: Immediate response required.",
                            False  # Unread for responders
                        ))
            
            for i, (user_id, alert_id, emergency_id, notif_type, message, is_read) in enumerate(notifications, 1):
                notification_id = str(uuid.uuid4())
                logger.info(f"Attempting to seed notification {i} with ID: {notification_id}")
                
                await execute_query(
                    """
                    INSERT INTO notifications (
                        id, user_id, alert_id, emergency_id, type, message, is_read, created_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (notification_id, user_id, alert_id, emergency_id, notif_type, message, is_read),
                    commit=True
                )
                
                logger.info(f"Notification {i} seeded (or already existed).")

        logger.info("Database seeding process completed successfully.")

    except Exception as e:
        logger.exception(f"Error seeding data: {str(e)}")
        raise