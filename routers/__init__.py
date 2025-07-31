from fastapi import APIRouter
from .auth import auth_router
from . import cart, orders, products, users, admin
router = APIRouter()
router.include_router(auth_router)
router.include_router(users.router)
router.include_router(products.router)
router.include_router(cart.router)
router.include_router(orders.router)
router.include_router(admin.router)