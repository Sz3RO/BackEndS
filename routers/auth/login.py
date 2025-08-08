from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.security import OAuth2PasswordRequestForm
from db import db
from core.security import verify_password, create_access_token

router = APIRouter()

@router.post("/login")
async def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends()):
    user = await db.users.find_one({"$or": [{"email": form_data.username}, {"phone": form_data.username}]})
    if not user or not verify_password(form_data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Email hoặc mật khẩu không đúng")

    token = create_access_token(data={"sub": user["email"]})

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,     # khi dev có thể tạm bỏ
        samesite="lax"
    )

    return {"message": "Đăng nhập thành công"}
