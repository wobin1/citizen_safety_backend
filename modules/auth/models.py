from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class UserRegister(BaseModel):
    username: str
    password: str
    role: Optional[str] = "citizen"

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: UUID
    username: str
    role: str
    created_at: str
    last_login_at: Optional[str]