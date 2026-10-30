import secrets
from datetime import datetime, timedelta, timezone

from ..auth import hash_password, issue_tokens, verify_password
from ..errors import Conflict, Forbidden, NotFound
from ..models import AddressInput, ProfileUpdate, Registration
from ..notifications import send_password_reset
from ..store import store


def register(body: Registration) -> dict:
    if any(user["email"].lower() == body.email.lower() for user in store.users.values()):
        raise Conflict("Email already registered")
    user_id = store.next_id("users")
    user = {
        "id": user_id,
        "email": body.email.lower(),
        "display_name": body.display_name,
        "phone": None,
        "password_hash": hash_password(body.password),
        "role": "customer",
        "active": True,
    }
    store.users[user_id] = user
    return {key: user[key] for key in ("id", "email", "display_name")}


def login(email: str, password: str) -> dict:
    user = next((item for item in store.users.values() if item["email"] == email.lower()), None)
    if not user or not verify_password(password, user["password_hash"]):
        raise Forbidden("Email or password is incorrect")
    return issue_tokens(user["id"], user["role"])


def refresh(refresh_token: str) -> dict:
    user_id = store.refresh_tokens.pop(refresh_token, None)
    user = store.users.get(user_id) if user_id else None
    if not user or not user["active"]:
        raise Forbidden("Refresh token is invalid")
    return issue_tokens(user["id"], user["role"])


async def request_password_reset(email: str) -> None:
    user = next((item for item in store.users.values() if item["email"] == email.lower()), None)
    if not user:
        return
    token = secrets.token_urlsafe(32)
    store.reset_tokens[token] = {
        "user_id": user["id"],
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=20),
    }
    await send_password_reset(user["email"], token)


def confirm_password_reset(token: str, new_password: str) -> None:
    record = store.reset_tokens.pop(token, None)
    if not record or record["expires_at"] < datetime.now(timezone.utc):
        raise Forbidden("Reset token is invalid or expired")
    store.users[record["user_id"]]["password_hash"] = hash_password(new_password)


def update_profile(user_id: int, body: ProfileUpdate) -> dict:
    user = store.users[user_id]
    for key, value in body.model_dump(exclude_none=True).items():
        user[key] = value
    return {key: user.get(key) for key in ("id", "email", "display_name", "phone")}


def list_addresses(user_id: int) -> list[dict]:
    return [address for address in store.snapshot("addresses") if address["owner_id"] == user_id]


def create_address(user_id: int, body: AddressInput) -> dict:
    address_id = store.next_id("addresses", start=2000)
    address = {"id": address_id, "owner_id": user_id, **body.model_dump()}
    store.addresses[address_id] = address
    return address


def delete_address(user_id: int, address_id: int) -> None:
    address = store.addresses.get(address_id)
    if not address:
        raise NotFound("Address not found")
    if address["owner_id"] != user_id:
        raise NotFound("Address not found")
    del store.addresses[address_id]
