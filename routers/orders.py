from fastapi import APIRouter, Depends, HTTPException
from core.dependencies import get_current_user
from schemas.order import OrderCreate, OrderOut, OrderItem
from db import db
from datetime import datetime
import uuid

router = APIRouter(prefix="/orders", tags=["Orders"])

# GET /orders/ - Lấy danh sách đơn hàng của người dùng
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

# POST /orders/ - Tạo đơn hàng mới từ giỏ hàng
@router.post("/", response_model=dict)
async def create_order(current_user: dict = Depends(get_current_user)):
    cart = await db.carts.find_one({"user_id": str(current_user["_id"])})
    if not cart or not cart.get("items"):
        raise HTTPException(status_code=400, detail="Giỏ hàng trống")

    items = []
    total_price = 0

    # kiểm tra và trừ tồn kho
    for item in cart["items"]:
        product = await db.products.find_one({"_id": item["product_id"]})
        if not product:
            raise HTTPException(status_code=404, detail=f"Sản phẩm {item['product_id']} không tồn tại")

        if product.get("stock", 0) < item["quantity"]:
            raise HTTPException(
                status_code=400,
                detail=f"Sản phẩm '{product['name']}' không đủ hàng (còn {product.get('stock', 0)} cái)"
            )

        items.append({
            "product_id": item["product_id"],
            "quantity": item["quantity"],
            "price": product["price"]
        })
        total_price += product["price"] * item["quantity"]

        # trừ kho
        await db.products.update_one(
            {"_id": product["_id"]},
            {"$inc": {"stock": -item["quantity"]}}
        )

    order = {
        "_id": str(uuid.uuid4()),
        "user_id": str(current_user["_id"]),
        "items": items,
        "total_price": total_price,
        "status": "pending",
        "created_at": datetime.utcnow()
    }

    await db.orders.insert_one(order)
    await db.carts.update_one({"user_id": str(current_user["_id"])}, {"$set": {"items": []}})

    return {"message": "Đặt hàng thành công", "order_id": order["_id"]}

# GET /orders/{order_id} - Xem chi tiết đơn hàng
@router.get("/{order_id}", response_model=OrderOut)
async def get_order_detail(order_id: str, current_user: dict = Depends(get_current_user)):
    order = await db.orders.find_one({"_id": order_id, "user_id": str(current_user["_id"])})
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
    return {
        "id": str(order["_id"]),
        "user_id": order["user_id"],
        "items": order["items"],
        "total_price": order["total_price"],
        "status": order["status"],
        "created_at": order["created_at"]
    }

# DELETE /orders/{order_id} - Huỷ đơn hàng (chỉ nếu đang ở trạng thái 'pending')
@router.delete("/{order_id}")
async def cancel_order(order_id: str, current_user: dict = Depends(get_current_user)):
    order = await db.orders.find_one({"_id": order_id})
    if not order or order["user_id"] != str(current_user["_id"]):
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")

    if order["status"] != "pending":
        raise HTTPException(status_code=400, detail="Chỉ được huỷ đơn hàng ở trạng thái 'pending'")

    await db.orders.update_one({"_id": order_id}, {"$set": {"status": "cancelled"}})
    return {"message": "Đơn hàng đã được huỷ"}
