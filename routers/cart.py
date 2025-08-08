from fastapi import APIRouter, Depends, HTTPException
from core.dependencies import get_current_user
from schemas.cart import CartItem, CartUpdate, CartOut
from db import db

router = APIRouter(prefix="/cart", tags=["Cart"])

# GET /cart/ - Lấy giỏ hàng hiện tại
@router.get("/", response_model=CartOut)
async def get_cart(current_user: dict = Depends(get_current_user)):
    cart = await db.carts.find_one({"user_id": str(current_user["_id"])})
    if not cart:
        return {"user_id": str(current_user["_id"]), "items": []}
    return {"user_id": str(current_user["_id"]), "items": cart.get("items", [])}

# POST /cart/add - Thêm sản phẩm vào giỏ
@router.post("/add")
async def add_to_cart(item: CartItem, current_user: dict = Depends(get_current_user)):
    cart = await db.carts.find_one({"user_id": str(current_user["_id"])})
    if not cart:
        cart = {"user_id": str(current_user["_id"]), "items": []}

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

# PUT /cart/update - Cập nhật số lượng sản phẩm trong giỏ
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
        raise HTTPException(status_code=404, detail="Sản phẩm không có trong giỏ hàng")

    await db.carts.update_one(
        {"user_id": cart["user_id"]},
        {"$set": {"items": cart["items"]}}
    )
    return {"message": "Đã cập nhật giỏ hàng"}

# DELETE /cart/remove/{product_id} - Xoá 1 sản phẩm khỏi giỏ
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

# DELETE /cart/clear - Xoá toàn bộ giỏ hàng
@router.delete("/clear")
async def clear_cart(current_user: dict = Depends(get_current_user)):
    result = await db.carts.update_one(
        {"user_id": str(current_user["_id"])},
        {"$set": {"items": []}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Không tìm thấy giỏ hàng hoặc giỏ hàng đã trống")
    return {"message": "Đã xoá toàn bộ giỏ hàng"}
