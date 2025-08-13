from pydantic import BaseModel
from typing import List
from datetime import datetime

class OrderItem(BaseModel):
    product_id: str
    quantity: int
    price: float
    color: str
    size: str

class OrderCreate(BaseModel):
    items: List[OrderItem]

class OrderOut(BaseModel):
    id: str
    user_id: str
    items: List[OrderItem]
    total_price: float
    status: str
    created_at: datetime
