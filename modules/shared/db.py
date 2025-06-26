import os
import asyncio
from contextlib import asynccontextmanager

from dotenv import load_dotenv
import asyncpg  # Changed from psycopg2 to asyncpg
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Database connection pool (asyncpg pool)
db_pool = None

async def init_db():
    """
    Initialize asynchronous database connection pool.
    This function should be called once at application startup.
    """
    global db_pool
    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            logger.error("DATABASE_URL environment variable is not set.")
            raise RuntimeError("DATABASE_URL environment variable is not set.")

        logger.info("Initializing database connection pool...")
        db_pool = await asyncpg.create_pool(
            dsn=database_url,
            min_size=1,
            max_size=20,
            command_timeout=60, # Optional: timeout for commands
        )
        logger.info("Database connection pool initialized successfully.")
    except Exception as e:
        logger.exception(f"Error initializing database: {str(e)}")
        raise

async def close_db():
    """
    Close the database connection pool.
    This function should be called once at application shutdown.
    """
    global db_pool
    if db_pool:
        logger.info("Closing database connection pool...")
        await db_pool.close()
        logger.info("Database connection pool closed.")

async def create_tables():
    """
    Execute SQL schema file to create tables.
    This function should be called after init_db, typically at application startup.
    """
    try:
        schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'schema.sql')
        logger.info(f"Reading schema from {schema_path}...")
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        logger.info("Executing schema SQL to create/update tables...")
        async with get_db_connection() as conn:
            await conn.execute(schema_sql)
            logger.info("Database tables created/updated successfully.")
    except FileNotFoundError:
        logger.error(f"Error: schema.sql not found at {schema_path}")
        raise
    except Exception as e:
        logger.exception(f"Error creating tables: {str(e)}")
        raise

@asynccontextmanager
async def get_db_connection():
    """
    Asynchronous context manager for acquiring and releasing database connections from the pool.
    Use with 'async with get_db_connection() as conn:'
    """
    global db_pool
    if db_pool is None:
        logger.error("Database connection pool is not initialized. Call init_db() first.")
        raise RuntimeError("Database connection pool is not initialized. Call init_db() first.")
    
    conn = None
    try:
        logger.debug("Acquiring database connection from pool...")
        conn = await db_pool.acquire()
        logger.debug("Database connection acquired.")
        yield conn
    finally:
        if conn:
            logger.debug("Releasing database connection back to pool...")
            await db_pool.release(conn)
            logger.debug("Database connection released.")

async def execute_query(sql, params=None, fetch_one=False, commit=False):
    """
    Execute an asynchronous SQL query and return results.
    Note: Use $1, $2, ... as placeholders in your SQL queries for parameters (not %s or %(name)s).
    """
    try:
        logger.info(f"Executing SQL query: {sql.strip().splitlines()[0][:100]}... | Params: {params}")
        async with get_db_connection() as conn:
            if fetch_one:
                result = await conn.fetchrow(sql, *(params or []))
            else:
                result = await conn.fetch(sql, *(params or []))
            if commit and not sql.strip().upper().startswith("SELECT"):
                logger.debug("Commit requested, but asyncpg auto-commits simple statements.")
            logger.info("SQL query executed successfully.")
            return result
    except Exception as e:
        logger.exception(f"Database query error: {str(e)}")
        raise



