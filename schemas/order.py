from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class OrderItem(BaseModel):
    product_id: str
    quantity: int
    price: float

class OrderCreate(BaseModel):
    # có thể cho phép đặt trực tiếp mà không qua cart
    items: List[OrderItem]

class OrderOut(BaseModel):
    id: str
    user_id: str
    items: List[OrderItem]
    total_price: float
    status: str
    created_at: datetime
