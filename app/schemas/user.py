from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from app.models.domain import UserRole

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

class UserBase(BaseModel):
    username: str
    role: UserRole = UserRole.MANAGER

class UserCreate(UserBase):
    password: str
    org_id: UUID

class UserResponse(UserBase):
    id: UUID
    org_id: UUID
    
    model_config = ConfigDict(from_attributes=True)
