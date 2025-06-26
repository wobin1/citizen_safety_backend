import uuid
from .db import execute_query
from passlib.context import CryptContext

import logging

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def seed_data():
    """Seed initial data into the database"""
    try:
        logger.info("Starting database seeding process.")

        # --- Seed admin user ---
        # Generate a UUID for the admin, but if the username conflicts, do nothing.
        # We don't need to retrieve the ID for the admin user in this script's flow
        # as no other seed data directly depends on it.
        admin_id = str(uuid.uuid4())
        admin_password = pwd_context.hash("admin123")
        logger.info(f"Attempting to seed admin user 'admin' with ID: {admin_id}")
        await execute_query(
            """
            INSERT INTO users (id, username, password_hash, role, created_at)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (username) DO NOTHING
            """,
            (admin_id, "admin", admin_password, "admin"),
            commit=True # Important: Commit the insert immediately
        )
        logger.info("Admin user 'admin' seeded (or already existed).")


        # --- Seed sample citizen user and get its ID ---
        # Generate a UUID for the citizen. If a conflict occurs on username,
        # we still need the *existing* user's ID for the incident.
        citizen_username = "citizen1"
        citizen_password_hash = pwd_context.hash("citizen123")
        temp_citizen_id = str(uuid.uuid4()) # Temporary ID for the insert attempt

        logger.info(f"Attempting to seed citizen user '{citizen_username}' with a new ID: {temp_citizen_id}")
        
        # Insert the citizen user. Use RETURNING id to get the ID back if newly inserted.
        # If ON CONFLICT occurs, the DO NOTHING means RETURNING will not return anything.
        # So, we'll always query for the ID afterwards.
        await execute_query(
            """
            INSERT INTO users (id, username, password_hash, role, created_at)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (username) DO NOTHING;
            """,
            (temp_citizen_id, citizen_username, citizen_password_hash, "citizen"),
            commit=True # Commit the insert/conflict resolution immediately
        )
        logger.info(f"Citizen user '{citizen_username}' insert/conflict resolution complete.")

        # Now, explicitly query for the citizen user's ID to ensure we get the *actual* ID
        # from the database, whether it was newly created or already existed.
        citizen_user_record = await execute_query(
            """
            SELECT id FROM users WHERE username = $1;
            """,
            (citizen_username,), # Pass params as a tuple for a single parameter
            fetch_one=True
        )

        if not citizen_user_record:
            raise RuntimeError(f"Could not find citizen user '{citizen_username}' after seeding attempt.")
        
        # Extract the ID from the fetched record. asyncpg.Record objects can be accessed like dictionaries.
        citizen_id = str(citizen_user_record['id'])
        logger.info(f"Confirmed citizen user ID for '{citizen_username}': {citizen_id}")


        # --- Seed sample incident ---
        incident_id = str(uuid.uuid4())
        logger.info(f"Attempting to seed incident with ID: {incident_id} for user ID: {citizen_id}")
        
        await execute_query(
            """
            INSERT INTO incidents (id, user_id, type, description, status, created_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            ON CONFLICT (id) DO NOTHING
            """,
            (incident_id, uuid.UUID(citizen_id), "theft", "Sample theft incident", "PENDING"), # Ensure user_id is a UUID object
            commit=True # Commit the insert immediately
        )
        logger.info("Sample incident seeded (or already existed).")
        
        logger.info("Database seeding process completed successfully.")

    except Exception as e:
        logger.exception(f"Error seeding data: {str(e)}") # Using exc_info=True for full traceback
        raise

