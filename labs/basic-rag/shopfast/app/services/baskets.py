import secrets

from ..errors import InvalidOperation, NotFound
from ..models import BasketItemInput
from ..store import store


def create_basket(user_id: int) -> dict:
    basket_id = store.next_id("baskets", start=1001)
    basket = {"id": basket_id, "owner_id": user_id, "items": [], "coupon_code": None, "share_token": None}
    store.baskets[basket_id] = basket
    return basket


def owned_basket(user_id: int, basket_id: int) -> dict:
    basket = store.baskets.get(basket_id)
    if not basket or basket["owner_id"] != user_id:
        raise NotFound("Basket not found")
    return basket


def add_item(user_id: int, basket_id: int, item: BasketItemInput) -> dict:
    basket = owned_basket(user_id, basket_id)
    product = store.products.get(item.product_id)
    if not product or product["status"] != "active":
        raise NotFound("Product not found")
    if product["inventory"] < item.quantity:
        raise InvalidOperation("Requested quantity is unavailable")
    existing = next((line for line in basket["items"] if line["product_id"] == item.product_id), None)
    if existing:
        existing["quantity"] = min(existing["quantity"] + item.quantity, 20)
    else:
        basket["items"].append(item.model_dump())
    return basket


def remove_item(user_id: int, basket_id: int, product_id: int) -> dict:
    basket = owned_basket(user_id, basket_id)
    basket["items"] = [line for line in basket["items"] if line["product_id"] != product_id]
    return basket


def apply_coupon(user_id: int, basket_id: int, code: str) -> dict:
    basket = owned_basket(user_id, basket_id)
    coupon = store.coupons.get(code.upper())
    if not coupon or not coupon["active"] or coupon["uses"] >= coupon["max_uses"]:
        raise InvalidOperation("Coupon is not available")
    basket["coupon_code"] = coupon["code"]
    return basket


def create_share_link(user_id: int, basket_id: int) -> dict:
    basket = owned_basket(user_id, basket_id)
    basket["share_token"] = secrets.token_urlsafe(18)
    return {"basket_id": basket_id, "share_token": basket["share_token"]}


def read_shared_basket(share_token: str) -> dict:
    basket = next((item for item in store.baskets.values() if item["share_token"] == share_token), None)
    if not basket:
        raise NotFound("Shared basket not found")
    return {"id": basket["id"], "items": basket["items"], "coupon_code": basket["coupon_code"]}
