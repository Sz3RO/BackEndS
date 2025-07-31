from fastapi import APIRouter, HTTPException
from schemas.auth import ResetPasswordRequest
from core.security import get_password_hash
from jose import jwt, JWTError
from core.config import SECRET_KEY, ALGORITHM
from db import db

router = APIRouter()

@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest):
    try:
        payload = jwt.decode(data.token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=400, detail="Token không hợp lệ")
    except JWTError:
        raise HTTPException(status_code=400, detail="Token không hợp lệ")

    hashed_password = get_password_hash(data.new_password)
    await db.users.update_one({"email": email}, {"$set": {"password": hashed_password}})
    return {"message": "Đặt lại mật khẩu thành công"}
