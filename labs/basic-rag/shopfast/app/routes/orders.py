from fastapi import APIRouter, Depends

from ..auth import current_user
from ..errors import ShopFastError
from ..services import orders
from .common import as_http_error

router = APIRouter()


@router.get("")
def list_orders(user: dict = Depends(current_user)) -> list[dict]:
    return orders.list_customer_orders(user["id"])


@router.get("/{order_id}")
def get_order(order_id: int, user: dict = Depends(current_user)) -> dict:
    try:
        return orders.get_customer_order(user["id"], order_id)
    except ShopFastError as error:
        raise as_http_error(error) from error


@router.post("/{order_id}/cancel")
def cancel_order(order_id: int, user: dict = Depends(current_user)) -> dict:
    try:
        return orders.cancel_order(user["id"], order_id)
    except ShopFastError as error:
        raise as_http_error(error) from error
