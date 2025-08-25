from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class UserRegister(BaseModel):
    username: str
    email: str
    password: str
    role: Optional[str] = "citizen"

class UserLogin(BaseModel):
    email_or_username: str
    password: str

class UserResponse(BaseModel):
    id: UUID
    username: str
    email: str
    role: str
    created_at: str
    last_login_at: Optional[str]

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str