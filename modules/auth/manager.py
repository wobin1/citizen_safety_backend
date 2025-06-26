from uuid import uuid4
from modules.auth.models import UserRegister, UserLogin
from modules.auth.utils import hash_password, verify_password, decode_token, create_access_token
from modules.shared.db import execute_query
from modules.shared.response import success_response, error_response
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

async def register_user(user: UserRegister) -> dict:
    """Register a new user"""
    try:
        user_id = str(uuid4())
        hashed_password = hash_password(user.password)
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
            raise error_response("Username already exists", 400)
        return success_response({
            "id": result[0],
            "username": result[1],
            "role": result[2],
            "created_at": result[3].isoformat()
        }, "User registered successfully")
    except Exception as e:
        return error_response(str(e), 500)

async def login_user(user: UserLogin) -> dict:
    """Authenticate user and return JWT"""
    try:
        result = await execute_query(
            """
            SELECT id, username, password_hash, role FROM users
            WHERE username = $1
            """,
            (user.username,),
            fetch_one=True
        )
        if not result or not verify_password(user.password, result[2]):
            return error_response("Invalid credentials", 401)
        
        token = create_access_token({"sub": str(result[0]), "role": result[3]})
        await execute_query(
            """
            UPDATE users SET last_login_at = NOW()
            WHERE id = $1
            """,
            (result[0],),
            commit=True
        )
        return success_response({"token": token}, "Login successful")
    except Exception as e:
        return error_response(str(e), 500)

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Get current user from JWT"""
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
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
        raise HTTPException(status_code=401, detail="User not found")
    
    return {
        "id": result[0],
        "username": result[1],
        "role": result[2],
        "created_at": result[3].isoformat(),
        "last_login_at": result[4].isoformat() if result[4] else None
    }