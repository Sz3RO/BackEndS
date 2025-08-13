# dbadd.py — import bulk data từ data.json vào MongoDB (fashionDB.products)
import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# 1) Lấy kết nối DB tái sử dụng từ dự án của bạn
try:
    from db import db  # dùng db.products như hiện tại trong codebase của bạn
    _USING_PROJECT_DB = True
except Exception:
    _USING_PROJECT_DB = False

# 2) Nếu không import được db từ dự án, fallback dùng MONGO_URL (sửa nếu cần)
if not _USING_PROJECT_DB:
    from motor.motor_asyncio import AsyncIOMotorClient
    MONGO_URL = "mongodb+srv://CPL_FE_06_GR6:CPL_FE_06_GR6@cluster0.8euhvjw.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
  # đổi sang connection string của bạn nếu cần
    client = AsyncIOMotorClient(MONGO_URL)
    db = client.fashionDB

# 3) (Tuỳ chọn) dùng schema Pydantic nếu có để validate
ProductCreate = None
try:
    # tuỳ codebase: schemas.product.ProductCreate hoặc product.ProductCreate
    from schemas.product import ProductCreate  # type: ignore
except Exception:
    try:
        from product import ProductCreate  # type: ignore
    except Exception:
        ProductCreate = None  # không có schema cũng không sao

def to_uuid5_key(doc: Dict[str, Any]) -> str:
    """
    Tạo _id 'deterministic' để tránh duplicate khi import nhiều lần.
    Dùng name|category|price làm key.
    """
    base = f"{doc.get('name','').strip().lower()}|{doc.get('category','').strip().lower()}|{doc.get('price','')}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, base))

def normalize_doc(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Chuẩn hoá 1 document theo schema ProductCreate (nếu có), thêm server fields.
    """
    doc = dict(raw)

    # Convert kiểu cơ bản
    if "price" in doc:
        try:
            doc["price"] = float(doc["price"])
        except Exception:
            pass
    if "discount" in doc:
        try:
            doc["discount"] = float(doc["discount"])
        except Exception:
            pass
    if "review_count" in doc:
        try:
            doc["review_count"] = int(doc["review_count"])
        except Exception:
            pass

    # Bảo đảm các field danh sách
    for k in ("sizes", "colors", "images"):
        v = doc.get(k)
        if v is None:
            doc[k] = []
        elif not isinstance(v, list):
            doc[k] = [v]

    # Validate bằng Pydantic nếu có
    if ProductCreate:
        # dùng mode="json" để HttpUrl -> str
        doc = ProductCreate(**doc).model_dump(mode="json")

    # Thêm server-managed fields
    if "_id" not in doc or not isinstance(doc["_id"], str):
        doc["_id"] = to_uuid5_key(doc)
    if "seller_id" not in doc:
        doc["seller_id"] = "seed-script"
    if "created_at" not in doc:
        doc["created_at"] = datetime.now(timezone.utc)

    return doc

async def bulk_import(json_path: Path, collection_name: str = "products") -> None:
    if not json_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {json_path}")

    # Đọc JSON (hỗ trợ cả mảng hoặc object {"items":[...]})
    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "items" in data and isinstance(data["items"], list):
        items = data["items"]
    elif isinstance(data, list):
        items = data
    else:
        raise ValueError("Định dạng JSON không hợp lệ. Mong đợi một mảng các sản phẩm hoặc object có key 'items'.")

    # Chuẩn hoá dữ liệu
    docs: List[Dict[str, Any]] = [normalize_doc(x) for x in items]

    # Upsert theo _id (deterministic) để chạy nhiều lần không tạo trùng
    from pymongo import UpdateOne  # Motor dùng cùng API BulkWrite
    ops = [UpdateOne({"_id": d["_id"]}, {"$set": d}, upsert=True) for d in docs]

    result = await db[collection_name].bulk_write(ops, ordered=False)
    inserted = result.upserted_count
    modified = result.modified_count
    matched = result.matched_count

    print(f"Done. upserted: {inserted}, modified: {modified}, matched(existing): {matched}")

if __name__ == "__main__":
    # Usage:
    #   python dbadd.py                -> mặc định tìm ./data.json
    #   python dbadd.py /path/to/data.json
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data.json")
    asyncio.run(bulk_import(path))
