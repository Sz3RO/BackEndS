from fastapi import Request, HTTPException, status
from jose import jwt, JWTError
from core.config import SECRET_KEY, ALGORITHM
from db import db

async def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Không tìm thấy token, vui lòng đăng nhập lại",
        )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Token không hợp lệ")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token không hợp lệ")

    user = await db.users.find_one({"email": email})
    if user is None:
        raise HTTPException(status_code=401, detail="User không tồn tại")
    return user
