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

# Tổng số user
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

# Thống kê theo ngày gần đây
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
        {
            "$group": {
                "_id": "$items.product_id",
                "total_sold": {"$sum": "$items.quantity"},
                "total_revenue": {"$sum": {"$multiply": ["$items.quantity", "$items.price"]}}
            }
        },
        {"$sort": {"total_sold": -1}},
        {"$limit": limit}
    ]
    result = await db.orders.aggregate(pipeline).to_list(limit)
    # Lấy thông tin sản phẩm
    top_products = []
    for r in result:
        product = await db.products.find_one({"_id": r["_id"]})
        if product:
            top_products.append({
                "product_id": r["_id"],
                "name": product["name"],
                "total_sold": r["total_sold"],
                "total_revenue": r["total_revenue"]
            })
    return top_products
