from fastapi import APIRouter, Depends
from .models import UserRegister, UserLogin, UserResponse
from .manager import register_user, login_user, get_current_user
from modules.shared.response import success_response, error_response
router = APIRouter()

@router.post("/register")
async def register(user: UserRegister):
    """Register new user"""
    return await register_user(user)

@router.post("/login")
async def login(user: UserLogin):
    """Authenticate user"""
    return await login_user(user)

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user details"""
    return success_response(current_user, "User details retrieved")