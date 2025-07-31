from fastapi import APIRouter, Response

router = APIRouter()

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Đăng xuất thành công"}
