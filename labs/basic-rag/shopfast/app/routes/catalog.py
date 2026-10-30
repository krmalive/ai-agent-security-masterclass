from fastapi import APIRouter, Query

from ..errors import ShopFastError
from ..services import catalog
from .common import as_http_error

router = APIRouter()


@router.get("/products")
def search_products(
    q: str = Query(default="", max_length=100),
    category: str | None = Query(default=None, max_length=50),
    sort: str = "name",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    return catalog.search_products(q, category, sort, page, page_size)


@router.get("/products/{product_id}")
def get_product(product_id: int) -> dict:
    try:
        return catalog.get_product(product_id)
    except ShopFastError as error:
        raise as_http_error(error) from error
