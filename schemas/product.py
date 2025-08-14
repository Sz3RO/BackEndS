from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List
from datetime import datetime

class BaseProduct(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    gender: Optional[str] = None
    price: Optional[float] = Field(None, ge=0)
    stock: Optional[int] = Field(None, ge=0)
    sizes: Optional[List[str]] = None
    colors: Optional[List[str]] = None
    rating: Optional[float] = Field(None, ge=0, le=5)
    discount: Optional[float] = Field(None, ge=0, le=100)
    review_count: Optional[int] = Field(None, ge=0)
    images: Optional[List[HttpUrl]] = None
    description: Optional[str] = None
class ProductCreate(BaseProduct):
    name: str
    category: str
    gender: str
    price: float
    stock: int
    sizes: List[str]
    colors: List[str]
    rating: float
    discount: float
    review_count: int
    images: List[HttpUrl] = Field(default_factory=list)
    description: Optional[str] = None
class ProductUpdate(BaseProduct):
    pass

class ProductOut(ProductCreate):
    id: str
    seller_id: str
    created_at: datetime
