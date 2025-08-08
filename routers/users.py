from fastapi import APIRouter, Depends, HTTPException
from core.dependencies import get_current_user
from schemas.user import UserUpdate, ChangePassword, UserOut, BecomeSellerResponse
from core.security import verify_password, get_password_hash
from db import db

router = APIRouter(prefix="", tags=["Users"])

# GET /me - Lấy thông tin người dùng hiện tại
@router.get("/me", response_model=UserOut)
async def get_profile(current_user: dict = Depends(get_current_user)):
    return {
        "id": str(current_user["_id"]),
        "email": current_user["email"],
        "fullname": current_user["fullname"],
        "phone": current_user["phone"],
        "address": current_user["address"],
        "created_at": current_user["created_at"],
        "role": current_user.get("role", "user")
    }

# PUT /update-profile - Cập nhật thông tin cá nhân
@router.put("/update-profile")
async def update_profile(data: UserUpdate, current_user: dict = Depends(get_current_user)):
    update_data = {}
    if data.fullname:
        update_data["fullname"] = data.fullname
    if data.phone:
        update_data["phone"] = data.phone
    if data.address:
        update_data["address"] = data.address

    if update_data:
        await db.users.update_one({"email": current_user["email"]}, {"$set": update_data})
    return {"message": "Cập nhật thành công"}

# PUT /change-password - Đổi mật khẩu
@router.put("/change-password")
async def change_password(data: ChangePassword, current_user: dict = Depends(get_current_user)):
    if not verify_password(data.old_password, current_user["password"]):
        raise HTTPException(status_code=400, detail="Mật khẩu cũ không đúng")

    hashed_password = get_password_hash(data.new_password)
    await db.users.update_one({"email": current_user["email"]}, {"$set": {"password": hashed_password}})
    return {"message": "Đổi mật khẩu thành công"}

# PUT /become-seller - Nâng cấp thành người bán
@router.put("/become-seller", response_model=BecomeSellerResponse)
async def become_seller(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") == "seller":
        raise HTTPException(status_code=400, detail="Bạn đã là người bán rồi")

    await db.users.update_one(
        {"email": current_user["email"]},
        {"$set": {"role": "seller"}}
    )
    return {"message": "Chúc mừng! Bạn đã trở thành người bán", "role": "seller"}
