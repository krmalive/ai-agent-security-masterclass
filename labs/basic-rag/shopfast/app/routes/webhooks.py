import json

from fastapi import APIRouter, Header, HTTPException, Request

from ..payments import valid_webhook_signature
from ..store import store

router = APIRouter()


@router.post("/payments", status_code=202)
async def payment_webhook(
    request: Request,
    x_payment_signature: str = Header(alias="X-Payment-Signature"),
) -> dict:
    raw_body = await request.body()
    if not valid_webhook_signature(raw_body, x_payment_signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    event = json.loads(raw_body)
    if event["id"] in store.webhook_events:
        return {"accepted": True, "duplicate": True}
    store.webhook_events.add(event["id"])
    order = next((item for item in store.orders.values() if item.get("provider_payment_id") == event["data"]["payment_id"]), None)
    if order and event["type"] in {"payment.authorized", "payment.failed", "refund.completed"}:
        order["payment_status"] = event["type"].split(".", 1)[1]
    return {"accepted": True, "duplicate": False}
