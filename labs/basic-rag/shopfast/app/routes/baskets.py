from fastapi import APIRouter, Depends, Header, HTTPException

from ..auth import current_user
from ..errors import ShopFastError
from ..models import BasketItemInput, CheckoutRequest, CouponInput
from ..services import baskets, checkout
from .common import as_http_error

router = APIRouter()


@router.post("", status_code=201)
def create_basket(user: dict = Depends(current_user)) -> dict:
    return baskets.create_basket(user["id"])


@router.get("/{basket_id}")
def get_basket(basket_id: int, user: dict = Depends(current_user)) -> dict:
    try:
        return baskets.owned_basket(user["id"], basket_id)
    except ShopFastError as error:
        raise as_http_error(error) from error


@router.post("/{basket_id}/items")
def add_item(basket_id: int, body: BasketItemInput, user: dict = Depends(current_user)) -> dict:
    try:
        return baskets.add_item(user["id"], basket_id, body)
    except ShopFastError as error:
        raise as_http_error(error) from error


@router.delete("/{basket_id}/items/{product_id}")
def remove_item(basket_id: int, product_id: int, user: dict = Depends(current_user)) -> dict:
    try:
        return baskets.remove_item(user["id"], basket_id, product_id)
    except ShopFastError as error:
        raise as_http_error(error) from error


@router.post("/{basket_id}/coupon")
def apply_coupon(basket_id: int, body: CouponInput, user: dict = Depends(current_user)) -> dict:
    try:
        return baskets.apply_coupon(user["id"], basket_id, body.code)
    except ShopFastError as error:
        raise as_http_error(error) from error


@router.post("/{basket_id}/share")
def share_basket(basket_id: int, user: dict = Depends(current_user)) -> dict:
    try:
        return baskets.create_share_link(user["id"], basket_id)
    except ShopFastError as error:
        raise as_http_error(error) from error


@router.get("/shared/{share_token}")
def shared_basket(share_token: str) -> dict:
    try:
        return baskets.read_shared_basket(share_token)
    except ShopFastError as error:
        raise as_http_error(error) from error


@router.post("/{basket_id}/checkout", status_code=201)
async def checkout_basket(
    basket_id: int,
    body: CheckoutRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    user: dict = Depends(current_user),
) -> dict:
    if len(idempotency_key) < 12:
        raise HTTPException(status_code=400, detail="Idempotency-Key is too short")
    try:
        return await checkout.checkout(user, basket_id, body, idempotency_key)
    except ShopFastError as error:
        raise as_http_error(error) from error
