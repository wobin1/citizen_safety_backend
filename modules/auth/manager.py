import logging
from uuid import uuid4
from modules.auth.models import UserRegister, UserLogin, ForgotPasswordRequest, ResetPasswordRequest
from modules.auth.utils import hash_password, verify_password, decode_token, create_access_token, create_reset_token_jwt, verify_reset_token
from modules.shared.db import execute_query
from modules.shared.response import success_response, error_response
from modules.shared.email_service import send_password_reset_email
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
            INSERT INTO users (id, username, email, password_hash, role, created_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            RETURNING id, username, email, role, created_at
            """,
            (user_id, user.username, user.email, hashed_password, user.role),
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
            "email": result[2],
            "role": result[3],
            "created_at": result[4].isoformat()
        }, "User registered successfully")
    except Exception as e:
        logger.error(f"Error registering user '{user.username}': {e}")
        return error_response(str(e), 500)

async def login_user(user: UserLogin) -> dict:
    """Authenticate user and return JWT and user data"""
    logger.info(f"Attempting login for user: {user.email_or_username}")
    try:
        result = await execute_query(
            """
            SELECT id, username, email, password_hash, role, created_at, last_login_at FROM users
            WHERE username = $1 OR email = $1
            """,
            (user.email_or_username,),
            fetch_one=True
        )
        if not result:
            logger.warning(f"Login failed: User '{user.email_or_username}' not found.")
        if not result or not verify_password(user.password, result[3]):
            logger.warning(f"Login failed: Invalid credentials for user '{user.email_or_username}'.")
            return error_response("Invalid credentials", 401)
        
        token = create_access_token({"sub": str(result[0]), "role": result[4]})
        logger.info(f"User '{user.email_or_username}' authenticated successfully. Token generated.")
        await execute_query(
            """
            UPDATE users SET last_login_at = NOW()
            WHERE id = $1
            """,
            (result[0],),
            commit=True
        )
        logger.debug(f"Updated last_login_at for user id: {result[0]}")
        user_data = {
            "id": result[0],
            "username": result[1],
            "email": result[2],
            "role": result[4],
            "created_at": result[5].isoformat() if result[5] else None,
            "last_login_at": result[6].isoformat() if result[6] else None
        }
        return success_response({"token": token, "user": user_data}, "Login successful")
    except Exception as e:
        logger.error(f"Error logging in user '{user.email_or_username}': {e}")
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
        SELECT id, username, email, role, created_at, last_login_at 
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
        "email": result[2],
        "role": result[3],
        "created_at": result[4].isoformat(),
        "last_login_at": result[5].isoformat() if result[5] else None
    }

async def forgot_password(request: ForgotPasswordRequest) -> dict:
    """Generate password reset token and send reset email"""
    logger.info(f"Password reset requested for email: {request.email}")
    try:
        # Check if user exists with this email
        result = await execute_query(
            """
            SELECT id, username FROM users 
            WHERE email = $1
            """,
            (request.email,),
            fetch_one=True
        )
        
        if not result:
            logger.warning(f"Password reset requested for non-existent email: {request.email}")
            # Return success even if user doesn't exist for security
            return success_response({}, "If the email exists, a password reset link has been sent")
        
        user_id = result[0]
        username = result[1]
        
        # Generate reset token
        reset_token = create_reset_token_jwt(str(user_id))
        
        # Store reset token in database (you may want to create a password_reset_tokens table)
        await execute_query(
            """
            INSERT INTO password_reset_tokens (user_id, token, created_at, expires_at)
            VALUES ($1, $2, NOW(), NOW() + INTERVAL '1 hour')
            ON CONFLICT (user_id) DO UPDATE SET
                token = EXCLUDED.token,
                created_at = EXCLUDED.created_at,
                expires_at = EXCLUDED.expires_at
            """,
            (user_id, reset_token),
            commit=True
        )
        
        # Send password reset email
        email_sent = await send_password_reset_email(request.email, reset_token, username)
        
        if email_sent:
            logger.info(f"Password reset email sent successfully to {request.email}")
        else:
            logger.warning(f"Failed to send password reset email to {request.email}")
        
        return success_response({
            "message": "If the email exists, a password reset link has been sent"
        }, "Password reset email sent")
        
    except Exception as e:
        logger.error(f"Error processing password reset for {request.email}: {e}")
        return error_response("Failed to process password reset request", 500)

async def reset_password(request: ResetPasswordRequest) -> dict:
    """Reset user password using valid reset token"""
    logger.info("Password reset attempt with token")
    try:
        # Verify the reset token
        payload = verify_reset_token(request.token)
        if not payload:
            logger.warning("Invalid or expired reset token used")
            return error_response("Invalid or expired reset token", 400)
        
        user_id = payload["sub"]
        
        # Verify token exists in database and hasn't expired
        result = await execute_query(
            """
            SELECT user_id FROM password_reset_tokens 
            WHERE user_id = $1 AND token = $2 AND expires_at > NOW()
            """,
            (user_id, request.token),
            fetch_one=True
        )
        
        if not result:
            logger.warning(f"Reset token not found or expired for user: {user_id}")
            return error_response("Invalid or expired reset token", 400)
        
        # Hash the new password
        hashed_password = hash_password(request.new_password)
        
        # Update user password
        await execute_query(
            """
            UPDATE users SET password_hash = $1, last_login_at = NOW()
            WHERE id = $2
            """,
            (hashed_password, user_id),
            commit=True
        )
        
        # Delete the used reset token
        await execute_query(
            """
            DELETE FROM password_reset_tokens WHERE user_id = $1
            """,
            (user_id,),
            commit=True
        )
        
        logger.info(f"Password successfully reset for user: {user_id}")
        return success_response({}, "Password reset successfully")
        
    except Exception as e:
        logger.error(f"Error resetting password: {e}")
        return error_response("Failed to reset password", 500)