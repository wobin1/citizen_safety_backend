import logging
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
JWT_SECRET = os.getenv("JWT_SECRET")
ALGORITHM = "HS256"

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    logger.debug("Hashing password.")
    hashed = pwd_context.hash(password)
    logger.debug("Password hashed successfully.")
    return hashed

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    logger.debug("Verifying password.")
    result = pwd_context.verify(plain_password, hashed_password)
    logger.debug(f"Password verification result: {result}")
    return result

def create_access_token(data: dict, expires_delta: timedelta = timedelta(hours=24)):
    """Create JWT token"""
    logger.debug(f"Creating access token for data: {data}")
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
    logger.debug(f"Access token created. Expires at: {expire}")
    return token

def decode_token(token: str) -> dict:
    """Decode JWT token"""
    logger.debug("Decoding JWT token.")
    try:
        decoded = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        logger.debug(f"Token decoded successfully: {decoded}")
        return decoded
    except JWTError as e:
        logger.error(f"Failed to decode token: {e}")
        return None