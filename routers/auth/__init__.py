from fastapi import APIRouter
from . import register, login, forgot_password, reset_password, logout

auth_router = APIRouter(prefix="/auth", tags=["Auth"])
auth_router.include_router(register.router)
auth_router.include_router(login.router)
auth_router.include_router(logout.router)
auth_router.include_router(forgot_password.router)
auth_router.include_router(reset_password.router)