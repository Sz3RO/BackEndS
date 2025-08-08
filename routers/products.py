from fastapi import APIRouter, Depends, HTTPException, Query
from schemas.product import ProductCreate, ProductUpdate, ProductOut
from core.dependencies import get_current_user
from db import db
from datetime import datetime
import uuid
from typing import Optional

router = APIRouter(prefix="/products", tags=["Products"])

# GET /products/ - Danh sách sản phẩm với filter & tìm kiếm
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

        pipeline += [
            {"$sort": {"created_at": -1}},
            {"$skip": skip},
            {"$limit": limit}
        ]

        products = await db.products.aggregate(pipeline).to_list(length=limit)
        return {"products": products}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# GET /products/{product_id} - Chi tiết sản phẩm
@router.get("/{product_id}", response_model=ProductOut)
async def get_product(product_id: str):
    product = await db.products.find_one({"_id": product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại")
    return product

# POST /products - Tạo sản phẩm mới
@router.post("/", response_model=ProductOut)
async def create_product(product: ProductCreate, current_user: dict = Depends(get_current_user)):
    new_product = product.dict()
    new_product["_id"] = str(uuid.uuid4())
    new_product["seller_id"] = current_user["_id"]
    new_product["created_at"] = datetime.utcnow()
    await db.products.insert_one(new_product)
    return new_product

# PUT /products/{product_id} - Cập nhật sản phẩm
@router.put("/{product_id}", response_model=ProductOut)
async def update_product(product_id: str, update: ProductUpdate, current_user: dict = Depends(get_current_user)):
    existing = await db.products.find_one({"_id": product_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại")
    if existing["seller_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="Không có quyền cập nhật sản phẩm này")

    update_data = {k: v for k, v in update.dict().items() if v is not None}
    await db.products.update_one({"_id": product_id}, {"$set": update_data})
    return {**existing, **update_data}

# DELETE /products/{product_id} - Xoá sản phẩm
@router.delete("/{product_id}")
async def delete_product(product_id: str, current_user: dict = Depends(get_current_user)):
    product = await db.products.find_one({"_id": product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại")
    if product["seller_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="Không có quyền xoá sản phẩm này")

    await db.products.delete_one({"_id": product_id})
    return {"detail": "Đã xoá sản phẩm thành công"}
