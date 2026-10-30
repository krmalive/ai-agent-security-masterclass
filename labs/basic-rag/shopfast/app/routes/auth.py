from fastapi import APIRouter

from ..errors import ShopFastError
from ..models import Login, PasswordReset, PasswordResetRequest, RefreshRequest, Registration
from ..services import accounts
from .common import as_http_error

router = APIRouter()


@router.post("/register", status_code=201)
def register(body: Registration) -> dict:
    try:
        return accounts.register(body)
    except ShopFastError as error:
        raise as_http_error(error) from error


@router.post("/login")
def login(body: Login) -> dict:
    try:
        return accounts.login(body.email, body.password)
    except ShopFastError as error:
        raise as_http_error(error) from error


@router.post("/refresh")
def refresh(body: RefreshRequest) -> dict:
    try:
        return accounts.refresh(body.refresh_token)
    except ShopFastError as error:
        raise as_http_error(error) from error


@router.post("/password-reset/request", status_code=202)
async def request_reset(body: PasswordResetRequest) -> dict:
    await accounts.request_password_reset(body.email)
    return {"message": "If the account exists, reset instructions will be sent"}


@router.post("/password-reset/confirm")
def confirm_reset(body: PasswordReset) -> dict:
    try:
        accounts.confirm_password_reset(body.token, body.new_password)
        return {"message": "Password changed"}
    except ShopFastError as error:
        raise as_http_error(error) from error
