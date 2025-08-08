from fastapi import APIRouter, HTTPException
from db import db
from schemas.user import UserCreate
from core.security import get_password_hash
import uuid
from datetime import datetime

router = APIRouter()

@router.post("/register")
async def register(user: UserCreate):
    existing = await db.users.find_one({"email": user.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email đã tồn tại")

    new_user = {
        "_id": str(uuid.uuid4()),
        "email": user.email,
        "fullname": user.fullname,
        "phone": user.phone,
        "address": user.address,
        "password": get_password_hash(user.password),
        "created_at": datetime.utcnow()
    }
    await db.users.insert_one(new_user)
    return {"message": "Đăng ký thành công"}
