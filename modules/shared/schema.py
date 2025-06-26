from .db import get_db_connection

async def create_tables():
    """Create tables for the Citizen Safety Application"""
    schema_sql = """
    CREATE TABLE IF NOT EXISTS users (
        id UUID PRIMARY KEY,
        username VARCHAR(50) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        role VARCHAR(20) NOT NULL CHECK (role IN ('citizen', 'emergency_service', 'admin')),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        last_login_at TIMESTAMP WITH TIME ZONE
    );

    CREATE TABLE IF NOT EXISTS incidents (
        id UUID PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES users(id),
        type VARCHAR(50) NOT NULL CHECK (type IN ('theft', 'assault', 'fire', 'medical')),
        description TEXT NOT NULL,
        location_lat NUMERIC(9,6),
        location_lon NUMERIC(9,6),
        status VARCHAR(20) NOT NULL CHECK (status IN ('PENDING', 'VALIDATED', 'REJECTED', 'ACTION_TAKEN')) DEFAULT 'PENDING',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        validated_at TIMESTAMP WITH TIME ZONE,
        rejection_reason TEXT
    );

    CREATE TABLE IF NOT EXISTS alerts (
        id UUID PRIMARY KEY,
        trigger_source VARCHAR(50) NOT NULL CHECK (trigger_source IN ('emergency_service', 'sensor', 'manual')),
        type VARCHAR(50) NOT NULL CHECK (type IN ('active shooter', 'natural disaster', 'missing person')),
        message TEXT NOT NULL,
        location_lat NUMERIC(9,6),
        location_lon NUMERIC(9,6),
        radius_km NUMERIC(5,2),
        status VARCHAR(20) NOT NULL CHECK (status IN ('ACTIVE', 'COOLDOWN', 'RESOLVED')) DEFAULT 'ACTIVE',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        cooldown_until TIMESTAMP WITH TIME ZONE
    );
    """
    try:
        async with get_db_connection() as conn:
            await conn.execute(schema_sql)
    except Exception as e:
        print(f"Error creating tables: {str(e)}")
        raise