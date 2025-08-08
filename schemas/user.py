from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    email: EmailStr
    fullname: str
    phone: str
    address: str

class UserCreate(UserBase):
    password: str

class UserOut(UserBase):
    id: str
    created_at: datetime
    role: str

class UserUpdate(BaseModel):
    fullname: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None

class ChangePassword(BaseModel):
    old_password: str
    new_password: str

class BecomeSellerResponse(BaseModel):
    message: str
    role: str
