from fastapi import APIRouter, Depends, HTTPException
from core.dependencies import get_current_user
from schemas.order import OrderCreate, OrderOut, OrderItem
from db import db
from datetime import datetime
import uuid

router = APIRouter(prefix="/orders", tags=["Orders"])

# Lấy tất cả đơn hàng của user
@router.get("/", response_model=list[OrderOut])
async def list_orders(current_user: dict = Depends(get_current_user)):
    orders = await db.orders.find({"user_id": str(current_user["_id"])}).to_list(100)
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

# Tạo đơn hàng mới từ giỏ hàng
@router.post("/", response_model=dict)
async def create_order(current_user: dict = Depends(get_current_user)):
    cart = await db.carts.find_one({"user_id": str(current_user["_id"])})
    if not cart or not cart.get("items"):
        raise HTTPException(status_code=400, detail="Giỏ hàng trống")

    items = []
    total_price = 0

    # kiểm tra và trừ stock
    for item in cart["items"]:
        product = await db.products.find_one({"_id": item["product_id"]})
        if not product:
            raise HTTPException(status_code=404, detail=f"Sản phẩm {item['product_id']} không tồn tại")

        # kiểm tra tồn kho
        if product.get("stock", 0) < item["quantity"]:
            raise HTTPException(
                status_code=400,
                detail=f"Sản phẩm '{product['name']}' không đủ hàng (còn {product.get('stock', 0)} cái)"
            )

        # thêm item vào đơn hàng
        items.append({
            "product_id": item["product_id"],
            "quantity": item["quantity"],
            "price": product["price"]
        })
        total_price += product["price"] * item["quantity"]

        # trừ tồn kho
        await db.products.update_one(
            {"_id": item["product_id"]},
            {"$inc": {"stock": -item["quantity"]}}
        )

    # tạo đơn hàng
    order = {
        "_id": str(uuid.uuid4()),
        "user_id": str(current_user["_id"]),
        "items": items,
        "total_price": total_price,
        "status": "pending",
        "created_at": datetime.utcnow()
    }

    await db.orders.insert_one(order)

    # clear cart sau khi đặt
    await db.carts.update_one(
        {"user_id": str(current_user["_id"])},
        {"$set": {"items": []}}
    )

    return {"message": "Đơn hàng đã được tạo", "order_id": order["_id"]}

# Admin cập nhật trạng thái đơn hàng
@router.put("/{order_id}/status")
async def update_order_status(order_id: str, status: str, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới được cập nhật trạng thái")

    result = await db.orders.update_one({"_id": order_id}, {"$set": {"status": status}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")

    return {"message": f"Đã cập nhật trạng thái đơn hàng {order_id} thành {status}"}
