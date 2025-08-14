# routes/forgot_password.py
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from jose import jwt

from db import db
from schemas.auth import ForgotPasswordRequest
from core.email import send_email
from core.config import (
    SECRET_KEY, ALGORITHM,
    FRONTEND_URL, RESET_TOKEN_TTL_MINUTES
)

router = APIRouter()

@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest):
    # Không tiết lộ tài khoản có tồn tại hay không
    user = await db.users.find_one({"email": payload.email})

    if user:
        # 1) Tạo JWT ngắn hạn có jti để có thể chặn dùng lại
        jti = str(uuid.uuid4())
        exp = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_TTL_MINUTES)
        token = jwt.encode(
            {"sub": payload.email, "jti": jti, "exp": exp},
            SECRET_KEY,
            algorithm=ALGORITHM,
        )

        # 2) Lưu token metadata (khuyên dùng) để hỗ trợ single-use
        await db.password_tokens.update_one(
            {"jti": jti},
            {"$set": {
                "jti": jti,
                "email": payload.email,
                "expires_at": exp,
                "used": False,
                "created_at": datetime.utcnow(),
            }},
            upsert=True
        )

        # 3) Gửi email chứa link đặt lại (FE đọc token từ query)
        reset_link = f"{FRONTEND_URL}/reset?token={token}"
        subject = "Liên kết đặt lại mật khẩu"
        body = f"""
        <p>Xin chào,</p>
        <p>Nhấp vào liên kết sau để đặt lại mật khẩu (hiệu lực {RESET_TOKEN_TTL_MINUTES} phút):</p>
        <p><a href="{reset_link}">{reset_link}</a></p>
        <p>Nếu bạn không yêu cầu, hãy bỏ qua email này.</p>
        """

        try:
            send_email(payload.email, subject, body)
        except Exception:
            raise HTTPException(status_code=500, detail="Không gửi được email đặt lại mật khẩu. Vui lòng thử lại sau.")

    return {"message": "Nếu email tồn tại, chúng tôi đã gửi liên kết đặt lại mật khẩu."}
