# /routers/orders.py
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
            "items": o["items"],  # mỗi item có product_id, quantity, price, color, size
            "total_price": o["total_price"],
            "status": o["status"],
            "created_at": o["created_at"]
        } for o in orders
    ]

# POST /orders/ - Tạo đơn hàng mới từ các item đã tick (frontend chỉ gửi các item được tick)
@router.post("/", response_model=dict)
async def create_order(payload: OrderCreate, current_user: dict = Depends(get_current_user)):
    # Các item được tick sẽ được frontend đưa vào payload.items
    if not payload.items:
        raise HTTPException(status_code=400, detail="Không có sản phẩm nào được chọn")

    items_to_order: list[OrderItem] = payload.items

    # Tải giỏ của user để có thể loại bỏ đúng các item đã đặt sau khi tạo order
    cart = await db.carts.find_one({"user_id": str(current_user["_id"])})
    if not cart:
        # Không bắt buộc phải có cart để đặt (vì có thể đặt từ trang SP), nhưng vẫn nên kiểm tra tồn tại
        cart = {"items": []}

    order_items = []
    total_price = 0.0

    # Duyệt từng item đã tick, validate & trừ tồn
    for item in items_to_order:
        product = await db.products.find_one({"_id": item.product_id})
        if not product:
            raise HTTPException(status_code=404, detail=f"Sản phẩm {item.product_id} không tồn tại")

        # Lấy giá từ DB để tránh bị thao túng giá từ client
        unit_price = float(product["price"])

        if product.get("stock", 0) < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Sản phẩm '{product.get('name', item.product_id)}' không đủ hàng (còn {product.get('stock', 0)} cái)"
            )

        # Gom item để lưu vào đơn (đúng schema yêu cầu)
        order_items.append({
            "product_id": item.product_id,
            "quantity": item.quantity,
            "price": unit_price,
            "color": item.color,
            "size": item.size
        })

        total_price += unit_price * item.quantity

        # Trừ kho
        await db.products.update_one(
            {"_id": product["_id"]},
            {"$inc": {"stock": -item.quantity}}
        )

    # Tạo order
    order_doc = {
        "_id": str(uuid.uuid4()),
        "user_id": str(current_user["_id"]),
        "items": order_items,
        "total_price": total_price,
        "status": "pending",
        "created_at": datetime.utcnow()
    }

    await db.orders.insert_one(order_doc)

    # Loại bỏ đúng các item đã đặt khỏi giỏ hàng (nếu có trong giỏ)
    # match theo product_id + color + size để tránh xóa nhầm biến thể
    for it in order_items:
        await db.carts.update_one(
            {"user_id": str(current_user["_id"])},
            {
                "$pull": {
                    "items": {
                        "product_id": it["product_id"],
                        "color": it["color"],
                        "size": it["size"]
                    }
                }
            }
        )

    return {"message": "Đặt hàng thành công", "order_id": order_doc["_id"]}

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
