from datetime import datetime

from pydantic import BaseModel, Field


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50, examples=["바지"])
    price: int = Field(ge=1, examples=[10000])
    desc: str = Field(min_length=1, max_length=200, examples=["청바지"])

    image_url: str | None = None
    image_filename: str | None = None

class ItemPublic(BaseModel):
    id: int
    name: str
    price: int
    description: str
    image_url: str | None = None
    image_filename: str | None = None
    created_at: datetime 
    updated_at: datetime
