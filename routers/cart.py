from fastapi import APIRouter, Depends, HTTPException
from core.dependencies import get_current_user
from schemas.cart import CartItem, CartUpdate, CartOut
from db import db
from typing import Optional

router = APIRouter(prefix="/cart", tags=["Cart"])

def normalize_value(val) -> str:
    """Normalize null/undefined values to empty string"""
    return "" if val is None else str(val)

def find_cart_item_index(items: list, product_id: str, color: Optional[str], size: Optional[str]) -> int:
    """Find index of cart item by product_id, color, and size"""
    normalized_color = normalize_value(color)
    normalized_size = normalize_value(size)
    
    for i, item in enumerate(items):
        if (item.get("product_id") == product_id and 
            normalize_value(item.get("color")) == normalized_color and 
            normalize_value(item.get("size")) == normalized_size):
            return i
    return -1

# GET /cart/ - Lấy giỏ hàng hiện tại
@router.get("/", response_model=CartOut)
async def get_cart(current_user: dict = Depends(get_current_user)):
    cart = await db.carts.find_one({"user_id": str(current_user["_id"])})
    if not cart:
        return {"user_id": str(current_user["_id"]), "items": []}
    
    # Ensure all items have valid data
    items = cart.get("items", [])
    valid_items = []
    
    for item in items:
        if item.get("product_id") and item.get("quantity", 0) > 0:
            # Normalize item data
            normalized_item = {
                "product_id": item["product_id"],
                "color": normalize_value(item.get("color")),
                "size": normalize_value(item.get("size")),
                "quantity": max(1, int(item.get("quantity", 1)))
            }
            valid_items.append(normalized_item)
    
    return {"user_id": str(current_user["_id"]), "items": valid_items}

# POST /cart/add - Thêm sản phẩm vào giỏ
@router.post("/add")
async def add_to_cart(item: CartItem, current_user: dict = Depends(get_current_user)):
    if not item.product_id:
        raise HTTPException(status_code=400, detail="Product ID is required")
    
    if item.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than 0")
    
    cart = await db.carts.find_one({"user_id": str(current_user["_id"])})
    if not cart:
        cart = {"user_id": str(current_user["_id"]), "items": []}

    items = cart.get("items", [])
    
    # Normalize input values
    normalized_color = normalize_value(item.color)
    normalized_size = normalize_value(item.size)
    quantity = max(1, int(item.quantity))

    # Check if item already exists
    existing_index = find_cart_item_index(items, item.product_id, normalized_color, normalized_size)
    
    if existing_index >= 0:
        # Update existing item quantity
        items[existing_index]["quantity"] = items[existing_index].get("quantity", 0) + quantity
    else:
        # Add new item
        new_item = {
            "product_id": item.product_id,
            "color": normalized_color,
            "size": normalized_size,
            "quantity": quantity
        }
        items.append(new_item)

    await db.carts.update_one(
        {"user_id": str(current_user["_id"])},
        {"$set": {"items": items}},
        upsert=True
    )
    return {"message": "Đã thêm sản phẩm vào giỏ hàng"}

# PUT /cart/update - Cập nhật số lượng sản phẩm trong giỏ
@router.put("/update")
async def update_cart(data: CartUpdate, current_user: dict = Depends(get_current_user)):
    if not data.product_id:
        raise HTTPException(status_code=400, detail="Product ID is required")
    
    cart = await db.carts.find_one({"user_id": str(current_user["_id"])})
    if not cart:
        raise HTTPException(status_code=404, detail="Chưa có giỏ hàng")

    items = cart.get("items", [])
    
    # Normalize values
    src_color = normalize_value(data.old_color if data.old_color is not None else data.color)
    src_size = normalize_value(data.old_size if data.old_size is not None else data.size)
    dst_color = normalize_value(data.color)
    dst_size = normalize_value(data.size)
    quantity = max(0, int(data.quantity or 0))

    # Find source item
    src_idx = find_cart_item_index(items, data.product_id, src_color, src_size)
    if src_idx == -1:
        raise HTTPException(status_code=404, detail="Sản phẩm (biến thể nguồn) không có trong giỏ hàng")

    # If quantity is 0 or negative, remove item
    if quantity <= 0:
        items.pop(src_idx)
        await db.carts.update_one(
            {"user_id": str(current_user["_id"])}, 
            {"$set": {"items": items}}
        )
        return {"message": "Đã xóa sản phẩm khỏi giỏ hàng"}

    # If variant hasn't changed, just update quantity
    if src_color == dst_color and src_size == dst_size:
        items[src_idx]["quantity"] = quantity
    else:
        # Variant changed - check if destination already exists
        dst_idx = find_cart_item_index(items, data.product_id, dst_color, dst_size)
        if dst_idx != -1 and dst_idx != src_idx:
            # Merge with existing destination item
            items[dst_idx]["quantity"] = items[dst_idx].get("quantity", 0) + quantity
            # Remove source item (adjust index if needed)
            if src_idx < dst_idx:
                dst_idx -= 1
            items.pop(src_idx)
        else:
            # Update variant in place
            items[src_idx].update({
                "color": dst_color,
                "size": dst_size,
                "quantity": quantity
            })

    await db.carts.update_one(
        {"user_id": str(current_user["_id"])}, 
        {"$set": {"items": items}}
    )
    return {"message": "Đã cập nhật giỏ hàng"}

# DELETE /cart/remove - Xóa 1 sản phẩm khỏi giỏ
@router.delete("/remove")
async def remove_from_cart(data: CartUpdate, current_user: dict = Depends(get_current_user)):
    if not data.product_id:
        raise HTTPException(status_code=400, detail="Product ID is required")
    
    cart = await db.carts.find_one({"user_id": str(current_user["_id"])})
    if not cart:
        raise HTTPException(status_code=404, detail="Chưa có giỏ hàng")

    items = cart.get("items", [])
    normalized_color = normalize_value(data.color)
    normalized_size = normalize_value(data.size)
    
    # Find and remove item
    item_index = find_cart_item_index(items, data.product_id, normalized_color, normalized_size)
    if item_index == -1:
        raise HTTPException(status_code=404, detail="Sản phẩm không có trong giỏ hàng")
    
    items.pop(item_index)

    await db.carts.update_one(
        {"user_id": str(current_user["_id"])},
        {"$set": {"items": items}}
    )
    return {"message": "Đã xóa sản phẩm khỏi giỏ hàng"}

# DELETE /cart/clear - Xóa toàn bộ giỏ hàng
@router.delete("/clear")
async def clear_cart(current_user: dict = Depends(get_current_user)):
    result = await db.carts.update_one(
        {"user_id": str(current_user["_id"])},
        {"$set": {"items": []}},
        upsert=True
    )
    return {"message": "Đã xóa toàn bộ giỏ hàng"}