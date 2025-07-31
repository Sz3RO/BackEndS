from fastapi import APIRouter, HTTPException
from schemas.auth import ForgotPasswordRequest
from db import db
from core.security import create_access_token
from datetime import timedelta

router = APIRouter()

@router.post("/forgot-password")
async def forgot_password(data: ForgotPasswordRequest):
    user = await db.users.find_one({"email": data.email})
    if not user:
        raise HTTPException(status_code=404, detail="Email không tồn tại")

    reset_token = create_access_token({"sub": user["email"]}, expires_delta=timedelta(minutes=15))
    
    return {"message": "Reset token password đã được gửi", "reset_token": reset_token}
