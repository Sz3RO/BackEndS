from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    email: EmailStr
    username: str

class UserCreate(UserBase):
    password: str

class UserOut(UserBase):
    id: str
    created_at: datetime
    role: str

class UserUpdate(BaseModel):
    username: Optional[str] = None

class ChangePassword(BaseModel):
    old_password: str
    new_password: str

class BecomeSellerResponse(BaseModel):
    message: str
    role: str
