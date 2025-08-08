from fastapi import APIRouter, Depends, HTTPException
from core.dependencies import get_current_user
from db import db
from datetime import datetime, timedelta

router = APIRouter(prefix="/admin", tags=["Admin"])

# Middleware check admin
async def verify_admin(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới được truy cập")
    return current_user

# Tổng số người dùng
@router.get("/users-count")
async def users_count(current_user: dict = Depends(verify_admin)):
    count = await db.users.count_documents({})
    return {"total_users": count}

# Tổng số đơn hàng & doanh thu
@router.get("/orders-summary")
async def orders_summary(current_user: dict = Depends(verify_admin)):
    total_orders = await db.orders.count_documents({})
    pipeline = [
        {"$group": {"_id": None, "total_revenue": {"$sum": "$total_price"}}}
    ]
    revenue_data = await db.orders.aggregate(pipeline).to_list(1)
    total_revenue = revenue_data[0]["total_revenue"] if revenue_data else 0
    return {"total_orders": total_orders, "total_revenue": total_revenue}

# Thống kê doanh thu theo ngày
@router.get("/sales-by-day")
async def sales_by_day(days: int = 7, current_user: dict = Depends(verify_admin)):
    since = datetime.utcnow() - timedelta(days=days)
    pipeline = [
        {"$match": {"created_at": {"$gte": since}}},
        {
            "$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                "revenue": {"$sum": "$total_price"},
                "orders": {"$sum": 1}
            }
        },
        {"$sort": {"_id": 1}}
    ]
    result = await db.orders.aggregate(pipeline).to_list(None)
    return [{"date": r["_id"], "revenue": r["revenue"], "orders": r["orders"]} for r in result]

# Top sản phẩm bán chạy
@router.get("/top-products")
async def top_products(limit: int = 5, current_user: dict = Depends(verify_admin)):
    pipeline = [
        {"$unwind": "$items"},
        {"$group": {
            "_id": "$items.product_id",
            "total_quantity": {"$sum": "$items.quantity"}
        }},
        {"$sort": {"total_quantity": -1}},
        {"$limit": limit}
    ]
    top = await db.orders.aggregate(pipeline).to_list(limit)
    return top

# Xem danh sách người dùng
@router.get("/users")
async def get_all_users(current_user: dict = Depends(verify_admin)):
    users = await db.users.find({}).to_list(100)
    return [
        {
            "id": str(u["_id"]),
            "email": u["email"],
            "username": u.get("username", ""),
            "role": u.get("role", "user"),
            "created_at": u["created_at"]
        } for u in users
    ]

# Khoá người dùng
@router.put("/users/{user_id}/ban")
async def ban_user(user_id: str, current_user: dict = Depends(verify_admin)):
    result = await db.users.update_one({"_id": user_id}, {"$set": {"banned": True}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    return {"message": "Tài khoản đã bị khoá"}

# Xem tất cả đơn hàng toàn hệ thống
@router.get("/orders")
async def get_all_orders(current_user: dict = Depends(verify_admin)):
    orders = await db.orders.find({}).to_list(100)
    return [
        {
            "id": str(o["_id"]),
            "user_id": o["user_id"],
            "items": o["items"],
            "total_price": o["total_price"],
            "status": o["status"],
            "created_at": o["created_at"]
        } for o in orders
    ]

# Xem tất cả sản phẩm của mọi seller
@router.get("/products")
async def get_all_products(current_user: dict = Depends(verify_admin)):
    products = await db.products.find({}).to_list(100)
    return [
        {
            "id": str(p["_id"]),
            "name": p["name"],
            "category": p.get("category"),
            "price": p["price"],
            "stock": p.get("stock", 0),
            "seller_id": p.get("seller_id")
        } for p in products
    ]

# Xoá người dùng
@router.delete("/users/{user_id}")
async def delete_user(user_id: str, current_user: dict = Depends(verify_admin)):
    result = await db.users.delete_one({"_id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    return {"message": "Đã xoá người dùng thành công"}

@router.delete("/products/{product_id}")
async def delete_product_by_admin(product_id: str, current_user: dict = Depends(verify_admin)):
    result = await db.products.delete_one({"_id": product_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")
    return {"message": "Admin đã xoá sản phẩm thành công"}