from fastapi import APIRouter, Depends
from .models import UserRegister, UserLogin, UserResponse, ForgotPasswordRequest, ResetPasswordRequest
from .manager import register_user, login_user, get_current_user, forgot_password, reset_password
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

@router.post("/forgot-password")
async def forgot_password_endpoint(request: ForgotPasswordRequest):
    """Request password reset for user"""
    return await forgot_password(request)

@router.post("/reset-password")
async def reset_password_endpoint(request: ResetPasswordRequest):
    """Reset user password with valid token"""
    return await reset_password(request)