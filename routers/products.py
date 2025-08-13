from fastapi import APIRouter, Depends, HTTPException, Query
from schemas.product import ProductCreate, ProductUpdate, ProductOut
from core.dependencies import get_current_user
from db import db
from datetime import datetime
import uuid
from typing import Optional, Literal, List

router = APIRouter(prefix="/products", tags=["Products"])

def to_out(doc: dict) -> dict:
    return {"id": str(doc["_id"]), **{k: v for k, v in doc.items() if k != "_id"}}

def require_seller_or_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") not in {"seller", "admin"}:
        raise HTTPException(status_code=403, detail="Bạn không có quyền đăng sản phẩm")
    return user

def _sort_stage(has_query: bool, sort_by: str, sort_dir: Literal["asc", "desc"]):
    """Trả về $sort stage phù hợp. Nếu có q & sort_by='relevance' => dùng _score."""
    dir_num = 1 if sort_dir == "asc" else -1
    if has_query and sort_by == "relevance":
        return {"$sort": {"_score": dir_num, "_id": dir_num}}
    allowed = {"created_at", "price", "rating", "discount", "review_count", "name"}
    field = sort_by if sort_by in allowed else "created_at"
    return {"$sort": {field: dir_num, "_id": dir_num}}

@router.get("/")
async def get_products(
    q: Optional[str] = Query(None, description="Keyword để autocomplete theo name"),
    category: Optional[str] = None,
    gender: Optional[str] = None,
    sizes: Optional[List[str]] = Query(None),
    colors: Optional[List[str]] = Query(None),
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    sort_by: Literal["relevance", "created_at", "price", "rating", "discount", "review_count", "name"] = "relevance",
    sort_dir: Literal["asc", "desc"] = "desc",
    page: int = 1,
    limit: int = 20,
):
    skip = max(page - 1, 0) * max(limit, 1)

    # ----- $match filters chung -----
    match: dict = {}

    # visibility: exclude hidden
    match["hidden"] = {"$ne": True}

    if category:
        match["category"] = category
    if gender:
        match["gender"] = gender
    if sizes:
        match["sizes"] = {"$in": sizes}
    if colors:
        match["colors"] = {"$in": colors}
    if price_min is not None or price_max is not None:
        price_cond = {}
        if price_min is not None:
            price_cond["$gte"] = price_min
        if price_max is not None:
            price_cond["$lte"] = price_max
        if price_cond:
            match["price"] = price_cond

    pipeline: List[dict] = []
    if q:
        pipeline.append({
            "$search": {
                "index": "products",
                "compound": {
                    "should": [
                        {"autocomplete": {"query": q, "path": "name"}},
                        {"text": {"query": q, "path": ["category", "description"]}}
                    ],
                    "minimumShouldMatch": 1
                }
            }
        })
        pipeline.append({"$set": {"_score": {"$meta": "searchScore"}}})

    if match:
        pipeline.append({"$match": match})

    pipeline.append(_sort_stage(bool(q), sort_by, sort_dir))
    pipeline.extend([
        {"$facet": {
            "results": [
                {"$skip": skip},
                {"$limit": limit},
                {"$addFields": {"id": {"$toString": "$_id"}}},
                {"$project": {"_id": 0}}
            ],
            "meta": [{"$count": "total"}]
        }},
        {"$project": {
            "products": "$results",
            "total": {"$ifNull": [{"$arrayElemAt": ["$meta.total", 0]}, 0]}
        }}
    ])

    try:
        agg = await db.products.aggregate(pipeline).to_list(length=1)
        return agg[0] if agg else {"products": [], "total": 0}
    except Exception:
        # Fallback regex
        fallback_match = dict(match)
        if q:
            fallback_match["name"] = {"$regex": q, "$options": "i"}

        fallback_pipeline: List[dict] = []
        if fallback_match:
            fallback_pipeline.append({"$match": fallback_match})

        fb_sort_by = "created_at" if sort_by == "relevance" else sort_by
        fallback_pipeline.append(_sort_stage(False, fb_sort_by, sort_dir))
        fallback_pipeline.extend([
            {"$facet": {
                "results": [
                    {"$skip": skip},
                    {"$limit": limit},
                    {"$addFields": {"id": {"$toString": "$_id"}}},
                    {"$project": {"_id": 0}}
                ],
                "meta": [{"$count": "total"}]
            }},
            {"$project": {
                "products": "$results",
                "total": {"$ifNull": [{"$arrayElemAt": ["$meta.total", 0]}, 0]}
            }}
        ])
        agg = await db.products.aggregate(fallback_pipeline).to_list(length=1)
        return agg[0] if agg else {"products": [], "total": 0}


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(product_id: str):
    # visibility: exclude hidden
    if not (doc := await db.products.find_one({"_id": product_id, "hidden": {"$ne": True}})):
        # Ẩn coi như không tồn tại với public
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại")
    return to_out(doc)

@router.post("/", response_model=ProductOut)
async def create_product(product: ProductCreate, user: dict = Depends(require_seller_or_admin)):
    doc = {
        "_id": str(uuid.uuid4()),
        "seller_id": user["_id"],
        "created_at": datetime.utcnow(),
        **product.model_dump(exclude_none=True),  # images đã có default list trong schema
    }
    await db.products.insert_one(doc)
    return to_out(doc)

@router.put("/{product_id}", response_model=ProductOut)
async def update_product(product_id: str, update: ProductUpdate, current_user: dict = Depends(require_seller_or_admin)):
    existing = await db.products.find_one({"_id": product_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại")
    if current_user.get("role") != "admin" and existing["seller_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="Không có quyền cập nhật sản phẩm này")

    update_data = update.model_dump(exclude_none=True)
    if not update_data:
        return to_out(existing)

    await db.products.update_one({"_id": product_id}, {"$set": update_data})
    return to_out({**existing, **update_data})

@router.delete("/{product_id}")
async def delete_product(product_id: str, current_user: dict = Depends(require_seller_or_admin)):
    product = await db.products.find_one({"_id": product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại")
    if current_user.get("role") != "admin" and product["seller_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="Không có quyền xoá sản phẩm này")

    await db.products.delete_one({"_id": product_id})
    return {"detail": "Đã xoá sản phẩm thành công"}
