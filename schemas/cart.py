# schemas/cart.py
from pydantic import BaseModel
from typing import List, Optional

class CartItem(BaseModel):
    product_id: str
    quantity: int
    color: str
    size: str

class CartUpdate(BaseModel):
    product_id: str
    quantity: int
    color: str        # NEW color (nếu muốn đổi)
    size: str         # NEW size (nếu muốn đổi)
    old_color: Optional[str] = None   # OPTIONAL – để xác định biến thể cũ
    old_size: Optional[str] = None    # OPTIONAL – để xác định biến thể cũ

class CartOut(BaseModel):
    user_id: str
    items: List[CartItem]
