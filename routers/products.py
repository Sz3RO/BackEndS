from fastapi import APIRouter, Depends, HTTPException, Query
from schemas.product import ProductCreate, ProductUpdate, ProductOut
from core.dependencies import get_current_user
from db import db
from datetime import datetime
import uuid
from typing import Optional

router = APIRouter(prefix="/products", tags=["Products"])
# GET all products
@router.get("/", response_model=dict)
async def get_products(
    q: Optional[str] = Query(None, description="Từ khóa tìm kiếm"),
    category: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    seller_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, le=50)
):
    skip = (page - 1) * limit

    try:
        if q:
            # Search với Atlas Search
            pipeline = [
                {
                    "$search": {
                        "index": "vi",
                        "text": {
                            "query": q,
                            "path": ["name", "category"]
                        }
                    }
                }
            ]
        else:
            # Filter cơ bản
            filter_query = {}
            if category:
                filter_query["category"] = category
            if min_price is not None or max_price is not None:
                filter_query["price"] = {}
                if min_price is not None:
                    filter_query["price"]["$gte"] = min_price
                if max_price is not None:
                    filter_query["price"]["$lte"] = max_price
            if seller_id:
                filter_query["seller_id"] = seller_id

            pipeline = [{"$match": filter_query}]

        # Thêm phân trang và sort
        pipeline += [
            {"$sort": {"created_at": -1}},
            {"$skip": skip},
            {"$limit": limit}
        ]

        products = await db.products.aggregate(pipeline).to_list(length=limit)

        total = await db.products.count_documents(
            {} if q else (pipeline[0].get("$match", {}))
        )

        return {
            "page": page,
            "limit": limit,
            "total": total,
            "products": [
                {
                    "id": str(p["_id"]),
                    "name": p["name"],
                    "description": p.get("description"),
                    "price": p["price"],
                    "stock": p.get("stock", 0),
                    "category": p.get("category"),
                    "image": p.get("image"),
                    "seller_id": p.get("seller_id"),
                    "created_at": p["created_at"]
                }
                for p in products
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lấy sản phẩm: {str(e)}")

# GET one product
@router.get("/{product_id}", response_model=ProductOut)
async def get_product(product_id: str):
    product = await db.products.find_one({"_id": product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")
    return {
        "id": str(product["_id"]),
        "name": product["name"],
        "description": product.get("description"),
        "price": product["price"],
        "stock": product.get("stock", 0),
        "category": product.get("category"),
        "image": product.get("image"),   # ✅ trả về image
        "seller_id": product.get("seller_id"),
        "created_at": product["created_at"]
    }

# CREATE product (seller or admin)
@router.post("/", response_model=dict)
async def create_product(data: ProductCreate, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in ["seller", "admin"]:
        raise HTTPException(status_code=403, detail="Bạn không có quyền đăng sản phẩm")

    new_product = {
        "_id": str(uuid.uuid4()),
        "name": data.name,
        "description": data.description,
        "price": data.price,
        "stock": data.stock,
        "category": data.category,
        "image": data.image,  # ✅ lưu 1 ảnh
        "seller_id": str(current_user["_id"]),
        "created_at": datetime.utcnow()
    }
    await db.products.insert_one(new_product)
    return {"message": "Thêm sản phẩm thành công", "id": new_product["_id"]}

# UPDATE product
@router.put("/{product_id}")
async def update_product(product_id: str, data: ProductUpdate, current_user: dict = Depends(get_current_user)):
    product = await db.products.find_one({"_id": product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")

    if current_user.get("role") != "admin" and product["seller_id"] != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="Không có quyền sửa sản phẩm này")

    update_data = {k: v for k, v in data.dict().items() if v is not None}
    if update_data:
        await db.products.update_one({"_id": product_id}, {"$set": update_data})

    return {"message": "Cập nhật sản phẩm thành công"}

# DELETE product
@router.delete("/{product_id}")
async def delete_product(product_id: str, current_user: dict = Depends(get_current_user)):
    product = await db.products.find_one({"_id": product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")

    if current_user.get("role") != "admin" and product["seller_id"] != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="Không có quyền xóa sản phẩm này")

    await db.products.delete_one({"_id": product_id})
    return {"message": "Xóa sản phẩm thành công"}
