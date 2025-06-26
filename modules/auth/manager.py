import logging
from uuid import uuid4
from modules.auth.models import UserRegister, UserLogin
from modules.auth.utils import hash_password, verify_password, decode_token, create_access_token
from modules.shared.db import execute_query
from modules.shared.response import success_response, error_response
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

# Configure logger
logger = logging.getLogger("auth.manager")
logging.basicConfig(level=logging.INFO)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

async def register_user(user: UserRegister) -> dict:
    """Register a new user"""
    logger.info(f"Attempting to register user: {user.username}")
    try:
        user_id = str(uuid4())
        hashed_password = hash_password(user.password)
        logger.debug(f"Generated user_id: {user_id}, hashed_password: {hashed_password}")
        result = await execute_query(
            """
            INSERT INTO users (id, username, password_hash, role, created_at)
            VALUES ($1, $2, $3, $4, NOW())
            RETURNING id, username, role, created_at
            """,
            (user_id, user.username, hashed_password, user.role),
            commit=True,
            fetch_one=True
        )
        if not result:
            logger.warning(f"Registration failed: Username '{user.username}' may already exist.")
            raise error_response("Username already exists", 400)
        logger.info(f"User registered successfully: {result[1]} (id: {result[0]})")
        return success_response({
            "id": result[0],
            "username": result[1],
            "role": result[2],
            "created_at": result[3].isoformat()
        }, "User registered successfully")
    except Exception as e:
        logger.error(f"Error registering user '{user.username}': {e}")
        return error_response(str(e), 500)

async def login_user(user: UserLogin) -> dict:
    """Authenticate user and return JWT"""
    logger.info(f"Attempting login for user: {user.username}")
    try:
        result = await execute_query(
            """
            SELECT id, username, password_hash, role FROM users
            WHERE username = $1
            """,
            (user.username,),
            fetch_one=True
        )
        if not result:
            logger.warning(f"Login failed: User '{user.username}' not found.")
        if not result or not verify_password(user.password, result[2]):
            logger.warning(f"Login failed: Invalid credentials for user '{user.username}'.")
            return error_response("Invalid credentials", 401)
        
        token = create_access_token({"sub": str(result[0]), "role": result[3]})
        logger.info(f"User '{user.username}' authenticated successfully. Token generated.")
        await execute_query(
            """
            UPDATE users SET last_login_at = NOW()
            WHERE id = $1
            """,
            (result[0],),
            commit=True
        )
        logger.debug(f"Updated last_login_at for user id: {result[0]}")
        return success_response({"token": token}, "Login successful")
    except Exception as e:
        logger.error(f"Error logging in user '{user.username}': {e}")
        return error_response(str(e), 500)

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Get current user from JWT"""
    logger.debug("Decoding JWT token for current user.")
    payload = decode_token(token)
    if not payload:
        logger.warning("Invalid token provided.")
        raise HTTPException(status_code=401, detail="Invalid token")
    
    logger.info(f"Fetching user with id: {payload['sub']}")
    result = await execute_query(
        """
        SELECT id, username, role, created_at, last_login_at 
        FROM users 
        WHERE id = $1
        """,
        (payload["sub"],),
        fetch_one=True
    )
    if not result:
        logger.warning(f"User not found for id: {payload['sub']}")
        raise HTTPException(status_code=401, detail="User not found")
    
    logger.info(f"User fetched successfully: {result[1]} (id: {result[0]})")
    return {
        "id": result[0],
        "username": result[1],
        "role": result[2],
        "created_at": result[3].isoformat(),
        "last_login_at": result[4].isoformat() if result[4] else None
    }