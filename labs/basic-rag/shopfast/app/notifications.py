import httpx

from .config import settings


async def send_password_reset(email: str, reset_token: str) -> None:
    async with httpx.AsyncClient(timeout=5) as client:
        await client.post(
            f"{settings.email_api}/messages",
            json={"template": "password-reset", "to": email, "variables": {"reset_token": reset_token}},
        )


async def send_order_confirmation(email: str, order: dict) -> None:
    async with httpx.AsyncClient(timeout=5) as client:
        await client.post(
            f"{settings.email_api}/messages",
            json={"template": "order-confirmation", "to": email, "variables": {"order_id": order["id"], "total_cents": order["total_cents"]}},
        )
