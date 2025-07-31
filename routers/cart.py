from fastapi import APIRouter, Depends, HTTPException
from core.dependencies import get_current_user
from schemas.cart import CartItem, CartUpdate, CartOut
from db import db

router = APIRouter(prefix="/cart", tags=["Cart"])

# Lấy giỏ hàng hiện tại
@router.get("/", response_model=CartOut)
async def get_cart(current_user: dict = Depends(get_current_user)):
    cart = await db.carts.find_one({"user_id": str(current_user["_id"])})
    if not cart:
        return {"user_id": str(current_user["_id"]), "items": []}
    return {"user_id": str(current_user["_id"]), "items": cart.get("items", [])}

# Thêm sản phẩm vào giỏ
@router.post("/add")
async def add_to_cart(item: CartItem, current_user: dict = Depends(get_current_user)):
    cart = await db.carts.find_one({"user_id": str(current_user["_id"])})
    if not cart:
        cart = {"user_id": str(current_user["_id"]), "items": []}

    # Kiểm tra nếu sản phẩm đã có trong giỏ → cộng dồn số lượng
    for cart_item in cart["items"]:
        if cart_item["product_id"] == item.product_id:
            cart_item["quantity"] += item.quantity
            break
    else:
        cart["items"].append({"product_id": item.product_id, "quantity": item.quantity})

    await db.carts.update_one(
        {"user_id": cart["user_id"]},
        {"$set": {"items": cart["items"]}},
        upsert=True
    )
    return {"message": "Đã thêm sản phẩm vào giỏ hàng"}

# Cập nhật số lượng sản phẩm
@router.put("/update")
async def update_cart(data: CartUpdate, current_user: dict = Depends(get_current_user)):
    cart = await db.carts.find_one({"user_id": str(current_user["_id"])})
    if not cart:
        raise HTTPException(status_code=404, detail="Chưa có giỏ hàng")

    updated = False
    for item in cart["items"]:
        if item["product_id"] == data.product_id:
            item["quantity"] = data.quantity
            updated = True
            break
    if not updated:
        raise HTTPException(status_code=404, detail="Sản phẩm không có trong giỏ")

    await db.carts.update_one(
        {"user_id": cart["user_id"]},
        {"$set": {"items": cart["items"]}}
    )
    return {"message": "Cập nhật số lượng thành công"}

# Xóa sản phẩm khỏi giỏ
@router.delete("/remove/{product_id}")
async def remove_from_cart(product_id: str, current_user: dict = Depends(get_current_user)):
    cart = await db.carts.find_one({"user_id": str(current_user["_id"])})
    if not cart:
        raise HTTPException(status_code=404, detail="Chưa có giỏ hàng")

    cart["items"] = [item for item in cart["items"] if item["product_id"] != product_id]

    await db.carts.update_one(
        {"user_id": cart["user_id"]},
        {"$set": {"items": cart["items"]}}
    )
    return {"message": "Đã xóa sản phẩm khỏi giỏ hàng"}
