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
        if (cart_item["product_id"] == item.product_id and
            cart_item["color"] == item.color and
            cart_item["size"] == item.size):
            cart_item["quantity"] += item.quantity
            break
    else:
        cart["items"].append(item.dict())

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

    items = cart.get("items", [])

    def find_index(pid: str, color: str, size: str) -> int:
        for i, it in enumerate(items):
            if it.get("product_id") == pid and it.get("color") == color and it.get("size") == size:
                return i
        return -1

    # Xác định biến thể "cũ" để sửa (nếu có gửi old_* thì dùng; nếu không, dùng color/size hiện tại)
    src_color = data.old_color if data.old_color is not None else data.color
    src_size  = data.old_size  if data.old_size  is not None else data.size

    src_idx = find_index(data.product_id, src_color, src_size)
    if src_idx == -1:
        raise HTTPException(status_code=404, detail="Sản phẩm (biến thể nguồn) không có trong giỏ hàng")

    # Nếu số lượng <= 0: coi như xóa
    if data.quantity <= 0:
        items.pop(src_idx)
        await db.carts.update_one({"user_id": cart["user_id"]}, {"$set": {"items": items}})
        return {"message": "Đã xóa sản phẩm khỏi giỏ hàng"}

    # Đích: color/size mới theo payload (color/size hiện tại giữ nguyên nếu không đổi)
    dst_color = data.color
    dst_size  = data.size

    # Nếu không đổi biến thể: chỉ cập nhật quantity
    if dst_color == src_color and dst_size == src_size:
        items[src_idx]["quantity"] = data.quantity
    else:
        # Có đổi biến thể: nếu đích đã tồn tại -> gộp; nếu chưa -> đổi trực tiếp
        dst_idx = find_index(data.product_id, dst_color, dst_size)
        if dst_idx != -1:
            # Gộp số lượng vào dòng đích
            items[dst_idx]["quantity"] = int(items[dst_idx].get("quantity") or 0) + int(data.quantity)
            # Xóa dòng cũ
            # Lưu ý chỉ số khi pop: nếu src_idx < dst_idx thì pop trước không ảnh hưởng dst_idx vì ta không dùng nữa
            items.pop(src_idx)
        else:
            # Chuyển trực tiếp biến thể cũ thành biến thể mới
            items[src_idx]["color"] = dst_color
            items[src_idx]["size"] = dst_size
            items[src_idx]["quantity"] = data.quantity

    await db.carts.update_one({"user_id": cart["user_id"]}, {"$set": {"items": items}})
    return {"message": "Đã cập nhật giỏ hàng"}



# DELETE /cart/remove - Xoá 1 sản phẩm khỏi giỏ
@router.delete("/remove")
async def remove_from_cart(data: CartUpdate, current_user: dict = Depends(get_current_user)):
    cart = await db.carts.find_one({"user_id": str(current_user["_id"])})
    if not cart:
        raise HTTPException(status_code=404, detail="Chưa có giỏ hàng")

    cart["items"] = [
        item for item in cart["items"]
        if not (item["product_id"] == data.product_id and
                item["color"] == data.color and
                item["size"] == data.size)
    ]

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
