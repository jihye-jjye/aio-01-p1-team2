from datetime import datetime

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50, examples=["바지"])
    price: int = Field(ge=1, examples=[10000])


class ProductUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=50, examples=["청바지"])
    price: int = Field(ge=1, examples=[20000])


class ProductPublic(BaseModel):
    id: str = Field(examples=["20260721170435315246"])
    name: str
    price: int
    created_at: datetime
