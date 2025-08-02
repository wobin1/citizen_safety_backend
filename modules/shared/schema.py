from .db import get_db_connection
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_tables():
    """Create tables for the Citizen Safety Application"""
    schema_sql = """
        -- Users table: Stores user information
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            fcm_token TEXT,
            role VARCHAR(20) NOT NULL CHECK (role IN ('citizen', 'emergency_service', 'admin')),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            last_login_at TIMESTAMP WITH TIME ZONE
        );

        -- Incidents table: Stores reported incidents with optional media and location
        CREATE TABLE IF NOT EXISTS incidents (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            type VARCHAR(50) NOT NULL CHECK (type IN ('theft', 'assault', 'fire', 'medical')),
            description TEXT NOT NULL,
            location_lat NUMERIC(9,6),
            location_lon NUMERIC(9,6),
            image_url TEXT,
            voice_note_url TEXT,
            video_url TEXT,
            status VARCHAR(20) NOT NULL CHECK (status IN ('PENDING', 'VALIDATED', 'REJECTED', 'ACTION_TAKEN')) DEFAULT 'PENDING',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            validated_at TIMESTAMP WITH TIME ZONE,
            rejection_reason TEXT
        );

        -- Alerts table: Stores broadcast alerts
        CREATE TABLE IF NOT EXISTS alerts (
            id UUID PRIMARY KEY,
            trigger_source VARCHAR(50) NOT NULL CHECK (trigger_source IN ('emergency_service', 'sensor', 'manual')),
            type VARCHAR(50) NOT NULL CHECK (type IN ('active shooter', 'natural disaster', 'missing person')),
            message TEXT NOT NULL,
            broadcast_type VARCHAR(50) NOT NULL CHECK (broadcast_type IN ('broadcast_all', 'broadcast_neighborhood')),
            location_lat NUMERIC(9,6),
            location_lon NUMERIC(9,6),
            radius_km NUMERIC(5,2),
            status VARCHAR(20) NOT NULL CHECK (status IN ('ACTIVE', 'COOLDOWN', 'RESOLVED')) DEFAULT 'ACTIVE',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            cooldown_until TIMESTAMP WITH TIME ZONE
        );

        -- Emergency table: Stores urgent situations with required location
        CREATE TABLE IF NOT EXISTS emergency (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            type VARCHAR(50) NOT NULL CHECK (type IN ('medical_emergency', 'fire_emergency', 'crime_emergency', 'disaster_emergency')),
            description TEXT NOT NULL,
            location_lat NUMERIC(9,6) NOT NULL,
            location_lon NUMERIC(9,6) NOT NULL,
            image_url TEXT,
            voice_note_url TEXT,
            video_url TEXT,
            severity VARCHAR(20) NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')) DEFAULT 'MEDIUM',
            status VARCHAR(20) NOT NULL CHECK (status IN ('REPORTED', 'DISPATCHED', 'RESOLVED', 'CANCELLED')) DEFAULT 'REPORTED',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE,
            responder_id UUID REFERENCES users(id) ON DELETE SET NULL,
            response_time TIMESTAMP WITH TIME ZONE
        );

        -- Create standard indexes for location-based queries
        CREATE INDEX IF NOT EXISTS idx_incidents_location ON incidents (location_lat, location_lon);
        CREATE INDEX IF NOT EXISTS idx_emergency_location ON emergency (location_lat, location_lon);

        -- Create indexes for frequently queried fields
        CREATE INDEX IF NOT EXISTS idx_incidents_user_id ON incidents (user_id);
        CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents (status);
        CREATE INDEX IF NOT EXISTS idx_emergency_user_id ON emergency (user_id);
        CREATE INDEX IF NOT EXISTS idx_emergency_status ON emergency (status);
    """
    try:
        async with get_db_connection() as conn:
            async with conn.transaction():
                await conn.execute(schema_sql)
                logger.info("Database tables and indexes created successfully.")
    except Exception as e:
        logger.error(f"Error creating tables: {str(e)}")
        raise