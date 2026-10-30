import hashlib
import hmac

import httpx

from .config import settings


async def authorize_payment(payment_token: str, amount_cents: int, order_reference: str) -> dict:
    async with httpx.AsyncClient(timeout=7) as client:
        response = await client.post(
            f"{settings.payment_api}/v1/authorizations",
            json={"token": payment_token, "amount_cents": amount_cents, "currency": "USD", "reference": order_reference},
        )
        response.raise_for_status()
        return response.json()


async def request_refund(provider_payment_id: str, amount_cents: int, reason: str) -> dict:
    async with httpx.AsyncClient(timeout=7) as client:
        response = await client.post(
            f"{settings.payment_api}/v1/refunds",
            json={"payment_id": provider_payment_id, "amount_cents": amount_cents, "reason": reason},
        )
        response.raise_for_status()
        return response.json()


def valid_webhook_signature(body: bytes, supplied_signature: str) -> bool:
    expected = hmac.new(
        settings.payment_webhook_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, supplied_signature)
