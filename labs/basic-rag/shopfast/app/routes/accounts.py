from fastapi import APIRouter, Depends, Response

from ..auth import current_user
from ..errors import ShopFastError
from ..models import AddressInput, ProfileUpdate
from ..services import accounts
from .common import as_http_error

router = APIRouter()


@router.get("/profile")
def profile(user: dict = Depends(current_user)) -> dict:
    return {key: user.get(key) for key in ("id", "email", "display_name", "phone", "role")}


@router.patch("/profile")
def update_profile(body: ProfileUpdate, user: dict = Depends(current_user)) -> dict:
    return accounts.update_profile(user["id"], body)


@router.get("/addresses")
def list_addresses(user: dict = Depends(current_user)) -> list[dict]:
    return accounts.list_addresses(user["id"])


@router.post("/addresses", status_code=201)
def create_address(body: AddressInput, user: dict = Depends(current_user)) -> dict:
    return accounts.create_address(user["id"], body)


@router.delete("/addresses/{address_id}", status_code=204)
def delete_address(address_id: int, user: dict = Depends(current_user)) -> Response:
    try:
        accounts.delete_address(user["id"], address_id)
        return Response(status_code=204)
    except ShopFastError as error:
        raise as_http_error(error) from error
