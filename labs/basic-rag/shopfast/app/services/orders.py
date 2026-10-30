from ..errors import InvalidOperation, NotFound
from ..payments import request_refund
from ..store import store


def list_customer_orders(user_id: int) -> list[dict]:
    return [order for order in store.snapshot("orders") if order["owner_id"] == user_id]


def get_customer_order(user_id: int, order_id: int) -> dict:
    order = store.orders.get(order_id)
    if not order or order["owner_id"] != user_id:
        raise NotFound("Order not found")
    return order


def cancel_order(user_id: int, order_id: int) -> dict:
    order = get_customer_order(user_id, order_id)
    if order["status"] not in {"processing", "confirmed"}:
        raise InvalidOperation("Order can no longer be cancelled")
    order["status"] = "cancelled"
    return order


async def refund_order(order_id: int, amount_cents: int, reason: str) -> dict:
    order = store.orders.get(order_id)
    if not order:
        raise NotFound("Order not found")
    if amount_cents > order["total_cents"]:
        raise InvalidOperation("Refund exceeds captured amount")
    refund = await request_refund(order["provider_payment_id"], amount_cents, reason)
    order["refund"] = {"id": refund["id"], "amount_cents": amount_cents, "status": refund["status"]}
    return order
