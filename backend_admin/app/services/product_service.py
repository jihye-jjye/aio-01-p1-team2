# product_service.py
from app.schemas.product_schema import ProductCreate, ProductPublic, ProductUpdate
from app.core.supabase_config import get_supabase
from zoneinfo import ZoneInfo
from datetime import date, datetime

# 1. 입력
def product_create(product: ProductCreate) -> ProductPublic | None:
    supabase = get_supabase()
    now = datetime.now(ZoneInfo("Asia/Seoul"))

    result = (
        supabase.table("products")
         .insert(
            {
                "id": now.strftime("%Y%m%d%H%M%S%f"),
                "name": product.name,
                "price": product.price,
                "created_at": now.isoformat(),   # timestamptz
            }
        )
        .execute()
    )
    if not result.data:
        return None
    return ProductPublic.model_validate(result.data[0])

# 2. 전체조회
def product_get_all() -> list[ProductPublic]:
    supabase = get_supabase()
    result = (
        supabase.table("products")
        .select("*")
        .execute()
    )
    return [ProductPublic.model_validate(item) for item in result.data]

# 3. 한개조회
def product_get(product_id: str) -> ProductPublic | None:
    supabase = get_supabase()

    result = (
        supabase.table("products")
        .select("*")
        .eq("id", product_id)
        .execute()
    )
    if not result.data:
        return None
    return ProductPublic.model_validate(result.data[0])


# 4. 삭제
def product_delete(product_id: str) -> ProductPublic | None:
    supabase = get_supabase()
    result = (
        supabase.table("products")
        .delete()
        .eq("id", product_id)
        .execute()
    )
    if not result.data:
        return None
    return ProductPublic.model_validate(result.data[0])


# 5. 수정
def product_update(
    product_id: str,
    product: ProductUpdate,
) -> ProductPublic | None:
    supabase = get_supabase()

    result = (
        supabase.table("products")
        .update(
                {
                    "name": product.name,
                    "price": product.price,
                }
            )
            .eq("id", product_id)
            .execute()
    )
    if not result.data:
        return None
    return ProductPublic.model_validate(result.data[0])

# 6. 검색
def search(
        name : str | None = None, start_date : date | None = None , 
        end_date :date | None = None, min_price : int | None = None, max_price: int | None = None 
        ):
    """아이템 검색 기능"""
    supabase = get_supabase()

    result = (
        supabase.table("products")
        .select("*")
        
    )

    return result
