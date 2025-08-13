from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, Literal, List, Dict, Any
from datetime import datetime
from core.dependencies import get_current_user
from db import db

router = APIRouter(prefix="/admin", tags=["Admin"])

# ===================== Common & Guards =====================

async def verify_admin(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới được truy cập")
    return current_user

def _parse_iso(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except Exception:
        return None

def _date_match(start_date: Optional[str], end_date: Optional[str]) -> Dict[str, Any]:
    start = _parse_iso(start_date)
    end = _parse_iso(end_date)
    cond: Dict[str, Any] = {}
    if start is not None or end is not None:
        cond["created_at"] = {}
        if start is not None:
            cond["created_at"]["$gte"] = start
        if end is not None:
            cond["created_at"]["$lte"] = end
    return cond

def _facet_paginate(skip: int, limit: int, project: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {"$facet": {
            "results": [
                {"$sort": {"created_at": -1, "_id": -1}},
                {"$skip": skip},
                {"$limit": limit},
                {"$addFields": {"id": {"$toString": "$_id"}}},
                {"$project": project}
            ],
            "meta": [{"$count": "total"}]
        }},
        {"$project": {
            "results": "$results",
            "total": {"$ifNull": [{"$arrayElemAt": ["$meta.total", 0]}, 0]}
        }}
    ]

async def _restock_if_needed(order: dict, old_status: str, new_status: str):
    """
    Khi chuyển trạng thái sang cancelled/refunded lần đầu => hoàn kho từng item.
    Không hoàn lại nếu đã ở cancelled/refunded trước đó để tránh cộng đôi.
    """
    cancel_like = {"cancelled", "refunded"}
    if old_status in cancel_like:
        return
    if new_status in cancel_like:
        for it in order.get("items", []):
            pid = it["product_id"]
            qty = it["quantity"]
            await db.products.update_one({"_id": pid}, {"$inc": {"stock": qty}})

# ===================== Users =====================

@router.get("/users")
async def list_users(
    q: Optional[str] = Query(None, description="Từ khoá toàn văn: email/username/fullname/phone"),
    role: Optional[str] = Query(None),
    banned: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, le=100),
    current_user: dict = Depends(verify_admin),
):
    skip = (page - 1) * limit
    pipeline: List[Dict[str, Any]] = []

    if q:
        pipeline.append({
            "$search": {
                "index": "user_search",
                "text": {"query": q, "path": ["email", "username", "fullname", "phone"]}
            }
        })

    match: Dict[str, Any] = {}
    if role: match["role"] = role
    if banned is not None: match["banned"] = banned
    pipeline.append({"$match": match} if match else {"$match": {}})

    pipeline += _facet_paginate(
        skip, limit,
        {
            "_id": 0,
            "id": 1,
            "email": 1,
            "username": {"$ifNull": ["$username", ""]},
            "fullname": {"$ifNull": ["$fullname", ""]},
            "phone": {"$ifNull": ["$phone", ""]},
            "role": {"$ifNull": ["$role", "user"]},
            "banned": {"$ifNull": ["$banned", False]},
            "created_at": 1
        }
    )

    agg = await db.users.aggregate(pipeline).to_list(1)
    if not agg:
        return {"users": [], "total": 0, "page": page, "limit": limit}
    return {"users": agg[0]["results"], "total": agg[0]["total"], "page": page, "limit": limit}


@router.get("/users/{user_id}")
async def get_user_detail(user_id: str, current_user: dict = Depends(verify_admin)):
    u = await db.users.find_one({"_id": user_id})
    if not u:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    return {
        "id": str(u["_id"]),
        "email": u.get("email"),
        "username": u.get("username", ""),
        "role": u.get("role", "user"),
        "banned": u.get("banned", False),
        "created_at": u.get("created_at"),
        "phone": u.get("phone"),
        "address": u.get("address"),
    }

@router.put("/users/{user_id}/ban")
async def ban_user(
    user_id: str,
    reason: Optional[str] = Query(None, description="Lý do ban (tuỳ chọn)"),
    current_user: dict = Depends(verify_admin),
):
    u = await db.users.find_one({"_id": user_id})
    if not u:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    if u.get("role") == "admin":
        raise HTTPException(status_code=403, detail="Không thể ban admin")
    if str(current_user.get("_id")) == user_id:
        raise HTTPException(status_code=400, detail="Không thể tự ban chính mình")

    await db.users.update_one(
        {"_id": user_id},
        {"$set": {"banned": True, "banned_reason": reason, "banned_at": datetime.utcnow()}}
    )
    return {"message": "Đã ban người dùng", "user_id": user_id, "reason": reason}

@router.put("/users/{user_id}/unban")
async def unban_user(user_id: str, current_user: dict = Depends(verify_admin)):
    u = await db.users.find_one({"_id": user_id})
    if not u:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")

    await db.users.update_one(
        {"_id": user_id},
        {"$set": {"banned": False}, "$unset": {"banned_reason": "", "banned_at": ""}}
    )
    return {"message": "Đã gỡ ban người dùng", "user_id": user_id}

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    purge_products: bool = Query(False, description="Xoá luôn sản phẩm nếu user là seller"),
    current_user: dict = Depends(verify_admin),
):
    u = await db.users.find_one({"_id": user_id})
    if not u:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    if u.get("role") == "admin":
        raise HTTPException(status_code=403, detail="Không thể xoá admin")
    if str(current_user.get("_id")) == user_id:
        raise HTTPException(status_code=400, detail="Không thể tự xoá chính mình")

    # dọn giỏ hàng
    await db.carts.delete_one({"user_id": user_id})

    # tùy chọn xoá sản phẩm sở hữu (nếu là seller)
    purged = 0
    if purge_products and u.get("role") == "seller":
        res = await db.products.delete_many({"seller_id": user_id})
        purged = res.deleted_count

    # giữ nguyên orders để bảo toàn lịch sử
    await db.users.delete_one({"_id": user_id})

    return {"message": "Đã xoá người dùng", "user_id": user_id, "purged_products": purged}

@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    role: Literal["user", "seller", "admin"],
    current_user: dict = Depends(verify_admin),
):
    u = await db.users.find_one({"_id": user_id})
    if not u:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    if str(current_user.get("_id")) == user_id and role != "admin":
        # tránh tự vô hiệu quyền admin của chính mình
        raise HTTPException(status_code=400, detail="Không thể đổi role làm mất quyền admin của chính mình")

    await db.users.update_one({"_id": user_id}, {"$set": {"role": role}})
    return {"message": "Đã cập nhật vai trò", "user_id": user_id, "role": role}

# ===================== Orders =====================

@router.get("/orders")
async def list_all_orders(
    user_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None, description="ISO date, ví dụ 2025-08-01"),
    end_date: Optional[str] = Query(None, description="ISO date, ví dụ 2025-08-31"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, le=100),
    current_user: dict = Depends(verify_admin)
):
    skip = (page - 1) * limit
    match: Dict[str, Any] = {}
    if user_id: match["user_id"] = user_id
    if status: match["status"] = status
    dm = _date_match(start_date, end_date)
    if dm: match.update(dm)

    pipeline = [{"$match": match} if match else {"$match": {}}] + _facet_paginate(
        skip,
        limit,
        {"_id": 0, "id": 1, "user_id": 1, "items": 1, "total_price": 1, "status": 1, "created_at": 1}
    )
    agg = await db.orders.aggregate(pipeline).to_list(1)
    if not agg:
        return {"orders": [], "total": 0, "page": page, "limit": limit}
    return {"orders": agg[0]["results"], "total": agg[0]["total"], "page": page, "limit": limit}

@router.put("/orders/{order_id}/status")
async def admin_update_order_status(
    order_id: str,
    new_status: Literal["pending","confirmed","processing","shipped","completed","cancelled","refunded"],
    current_user: dict = Depends(verify_admin)
):
    order = await db.orders.find_one({"_id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")

    old_status = order.get("status", "pending")
    if old_status == new_status:
        return {"message": "Trạng thái không đổi", "order_id": order_id, "status": new_status}

    # hoàn kho nếu chuyển sang cancelled/refunded
    await _restock_if_needed(order, old_status, new_status)

    await db.orders.update_one({"_id": order_id}, {"$set": {"status": new_status}})
    return {"message": "Đã cập nhật trạng thái đơn", "order_id": order_id, "status": new_status}

# ===================== Products (Moderation) =====================

@router.get("/products")
async def list_all_products(
    q: Optional[str] = Query(None),
    seller_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    has_discount: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, le=100),
    current_user: dict = Depends(verify_admin)
):
    skip = (page - 1) * limit
    match: Dict[str, Any] = {}
    if seller_id: match["seller_id"] = seller_id
    if category: match["category"] = category
    if has_discount is True: match["discount"] = {"$gt": 0}
    if q:
        match["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"category": {"$regex": q, "$options": "i"}}
        ]

    pipeline = [{"$match": match} if match else {"$match": {}}] + _facet_paginate(
        skip,
        limit,
        {
            "_id": 0, "id": 1, "name": 1, "price": 1, "stock": 1, "discount": 1,
            "rating": 1, "review_count": 1, "seller_id": 1, "category": 1,
            "created_at": 1, "images": 1, "gender": 1, "colors": 1, "sizes": 1,
            "hidden": {"$ifNull": ["$hidden", False]},
            "featured": {"$ifNull": ["$featured", False]},
        }
    )
    agg = await db.products.aggregate(pipeline).to_list(1)
    if not agg:
        return {"products": [], "total": 0, "page": page, "limit": limit}
    return {"products": agg[0]["results"], "total": agg[0]["total"], "page": page, "limit": limit}

@router.put("/products/{product_id}/visibility")
async def set_product_visibility(
    product_id: str,
    hidden: bool,
    current_user: dict = Depends(verify_admin)
):
    prod = await db.products.find_one({"_id": product_id})
    if not prod:
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại")
    await db.products.update_one({"_id": product_id}, {"$set": {"hidden": hidden}})
    return {"message": "Đã cập nhật hiển thị sản phẩm", "product_id": product_id, "hidden": hidden}

@router.put("/products/{product_id}/feature")
async def set_product_featured(
    product_id: str,
    featured: bool,
    current_user: dict = Depends(verify_admin)
):
    prod = await db.products.find_one({"_id": product_id})
    if not prod:
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại")
    await db.products.update_one({"_id": product_id}, {"$set": {"featured": featured}})
    return {"message": "Đã cập nhật featured", "product_id": product_id, "featured": featured}

# ===================== Stats =====================

@router.get("/stats/overview")
async def stats_overview(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: dict = Depends(verify_admin),
):
    dm = _date_match(start_date, end_date)
    include_status = ["confirmed", "processing", "shipped", "completed"]

    users_count = await db.users.count_documents({})
    products_count = await db.products.count_documents({})
    order_match: Dict[str, Any] = {}
    if dm: order_match.update(dm)
    total_orders = await db.orders.count_documents(order_match)

    status_pipe = [
        {"$match": order_match} if order_match else {"$match": {}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]
    status_rows = await db.orders.aggregate(status_pipe).to_list(50)
    order_by_status = {r["_id"] or "unknown": r["count"] for r in status_rows}

    rev_pipe = [
        {"$match": {**order_match, "status": {"$in": include_status}}} if order_match else
        {"$match": {"status": {"$in": include_status}}},
        {"$group": {"_id": None, "revenue": {"$sum": "$total_price"}}}
    ]
    rev_rows = await db.orders.aggregate(rev_pipe).to_list(1)
    revenue = (rev_rows[0]["revenue"] if rev_rows else 0) or 0

    return {
        "total_users": users_count,
        "total_products": products_count,
        "total_orders": total_orders,
        "order_by_status": order_by_status,
        "revenue": revenue
    }

@router.get("/stats/revenue")
async def stats_revenue_timeseries(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    granularity: Literal["day","week","month"] = "day",
    current_user: dict = Depends(verify_admin),
):
    include_status = ["confirmed", "processing", "shipped", "completed"]
    dm = _date_match(start_date, end_date)

    if granularity == "day":
        group_key = {
            "y": {"$year": "$created_at"},
            "m": {"$month": "$created_at"},
            "d": {"$dayOfMonth": "$created_at"},
        }
        project_date = {"$dateFromParts": {"year": "$_id.y", "month": "$_id.m", "day": "$_id.d"}}
    elif granularity == "week":
        group_key = {"y": {"$isoWeekYear": "$created_at"}, "w": {"$isoWeek": "$created_at"}}
        project_date = {"$dateFromParts": {"isoWeekYear": "$_id.y", "isoWeek": "$_id.w", "isoDayOfWeek": 1}}
    else:
        group_key = {"y": {"$year": "$created_at"}, "m": {"$month": "$created_at"}}
        project_date = {"$dateFromParts": {"year": "$_id.y", "month": "$_id.m", "day": 1}}

    pipeline = [
        {"$match": {**dm, "status": {"$in": include_status}}} if dm else
        {"$match": {"status": {"$in": include_status}}},
        {"$group": {"_id": group_key, "revenue": {"$sum": "$total_price"}, "orders": {"$sum": 1}}},
        {"$project": {"_id": 0, "date": project_date, "revenue": 1, "orders": 1}},
        {"$sort": {"date": 1}}
    ]
    rows = await db.orders.aggregate(pipeline).to_list(500)
    return {"series": rows, "granularity": granularity}

@router.get("/stats/top-products")
async def stats_top_products(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(verify_admin),
):
    include_status = ["confirmed", "processing", "shipped", "completed"]
    dm = _date_match(start_date, end_date)
    pipeline = [
        {"$match": {**dm, "status": {"$in": include_status}}} if dm else
        {"$match": {"status": {"$in": include_status}}},
        {"$unwind": "$items"},
        {"$group": {
            "_id": "$items.product_id",
            "qty": {"$sum": "$items.quantity"},
            "revenue": {"$sum": {"$multiply": ["$items.quantity", "$items.price"]}}
        }},
        {"$sort": {"qty": -1, "revenue": -1}},
        {"$limit": limit},
        {"$lookup": {
            "from": "products",
            "localField": "_id",
            "foreignField": "_id",
            "as": "product"
        }},
        {"$unwind": {"path": "$product", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "_id": 0,
            "product_id": {"$ifNull": ["$_id", ""]},
            "name": {"$ifNull": ["$product.name", ""]},
            "price": {"$ifNull": ["$product.price", None]},
            "qty": 1,
            "revenue": 1
        }}
    ]
    rows = await db.orders.aggregate(pipeline).to_list(limit)
    return {"top_products": rows}

@router.get("/stats/top-users")
async def stats_top_users(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(verify_admin),
):
    include_status = ["confirmed", "processing", "shipped", "completed"]
    dm = _date_match(start_date, end_date)
    pipeline = [
        {"$match": {**dm, "status": {"$in": include_status}}} if dm else
        {"$match": {"status": {"$in": include_status}}},
        {"$group": {
            "_id": "$user_id",
            "orders": {"$sum": 1},
            "spent": {"$sum": "$total_price"}
        }},
        {"$sort": {"spent": -1, "orders": -1}},
        {"$limit": limit},
        {"$lookup": {
            "from": "users",
            "localField": "_id",
            "foreignField": "_id",
            "as": "user"
        }},
        {"$unwind": {"path": "$user", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "_id": 0,
            "user_id": {"$ifNull": ["$_id", ""]},
            "email": {"$ifNull": ["$user.email", ""]},
            "fullname": {"$ifNull": ["$user.fullname", ""]},
            "orders": 1,
            "spent": 1
        }}
    ]
    rows = await db.orders.aggregate(pipeline).to_list(limit)
    return {"top_users": rows}
