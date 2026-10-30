from ..errors import NotFound
from ..store import store

ALLOWED_SORTS = {"name", "price_asc", "price_desc", "newest"}


def search_products(query: str, category: str | None, sort: str, page: int, page_size: int) -> dict:
    products = [item for item in store.snapshot("products") if item["status"] == "active"]
    if query:
        needle = query.casefold()
        products = [item for item in products if needle in f"{item['name']} {item['description']}".casefold()]
    if category:
        products = [item for item in products if item["category"] == category]
    if sort not in ALLOWED_SORTS:
        sort = "name"
    if sort == "price_asc":
        products.sort(key=lambda item: item["price_cents"])
    elif sort == "price_desc":
        products.sort(key=lambda item: item["price_cents"], reverse=True)
    else:
        products.sort(key=lambda item: item["name"])
    start = (page - 1) * page_size
    return {"items": products[start : start + page_size], "total": len(products), "page": page}


def get_product(product_id: int) -> dict:
    product = store.products.get(product_id)
    if not product or product["status"] != "active":
        raise NotFound("Product not found")
    return product
