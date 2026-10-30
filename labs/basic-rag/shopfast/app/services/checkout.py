from ..errors import Conflict, InvalidOperation, NotFound
from ..models import CheckoutRequest
from ..notifications import send_order_confirmation
from ..payments import authorize_payment
from ..store import store
from .baskets import owned_basket


def _totals(basket: dict) -> tuple[int, int, int]:
    subtotal = sum(store.products[line["product_id"]]["price_cents"] * line["quantity"] for line in basket["items"])
    discount = 0
    coupon = store.coupons.get(basket["coupon_code"]) if basket["coupon_code"] else None
    if coupon:
        discount = subtotal * coupon["value"] // 100 if coupon["kind"] == "percent" else coupon["value"]
    return subtotal, min(discount, subtotal), max(subtotal - discount, 0)


async def checkout(user: dict, basket_id: int, body: CheckoutRequest, idempotency_key: str) -> dict:
    if idempotency_key in store.idempotency_results:
        return store.idempotency_results[idempotency_key]
    basket = owned_basket(user["id"], basket_id)
    if not basket["items"]:
        raise InvalidOperation("Basket is empty")
    address = store.addresses.get(body.address_id)
    if not address or address["owner_id"] != user["id"]:
        raise NotFound("Shipping address not found")
    subtotal, discount, amount_due = _totals(basket)
    gift_applied = 0
    if body.gift_card_code:
        gift = store.gift_cards.get(body.gift_card_code)
        if not gift or gift["owner_id"] != user["id"]:
            raise InvalidOperation("Gift card is unavailable")
        gift_applied = min(gift["balance_cents"], amount_due)
        amount_due -= gift_applied
    order_id = store.next_id("orders", start=5000)
    payment = await authorize_payment(body.payment_token, amount_due, f"order-{order_id}")
    if payment.get("status") not in {"authorized", "pending"}:
        raise Conflict("Payment authorization failed")
    order = {
        "id": order_id,
        "owner_id": user["id"],
        "items": list(basket["items"]),
        "address": dict(address),
        "subtotal_cents": subtotal,
        "discount_cents": discount,
        "gift_card_cents": gift_applied,
        "total_cents": amount_due,
        "status": "processing",
        "payment_status": payment["status"],
        "provider_payment_id": payment["id"],
        "created_at": store.now(),
    }
    store.orders[order_id] = order
    store.idempotency_results[idempotency_key] = order
    basket["items"] = []
    await send_order_confirmation(user["email"], order)
    return order
