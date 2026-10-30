"""Internal Fulfillment API — guarded by a static bearer token.

The token is injected via the ORDERS_API_TOKEN env var. The *same* value is
stored in Vault KV at secret/orders-api by vault-init: the agent fetches it
from Vault at call time instead of carrying it in its own config. Try curling
this API without the token to see the 401 the agent never gets.
"""

import itertools
import os

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

API_TOKEN = os.environ["ORDERS_API_TOKEN"]

app = FastAPI(title="AcmeCorp Fulfillment API")

# Mirrors the order IDs seeded into Postgres so the two data sources agree.
ORDERS = {
    1001: {"item": "Mechanical keyboard", "status": "shipped", "carrier": "UPS", "eta_days": 2},
    1002: {"item": "USB-C dock", "status": "processing", "carrier": None, "eta_days": 5},
    1003: {"item": '27" 4K monitor', "status": "delivered", "carrier": "FedEx", "eta_days": 0},
    1004: {"item": "Noise-cancelling headset", "status": "shipped", "carrier": "DHL", "eta_days": 3},
    1005: {"item": "Standing desk", "status": "processing", "carrier": None, "eta_days": 7},
    1006: {"item": "Ergonomic chair", "status": "delivered", "carrier": "UPS", "eta_days": 0},
    1007: {"item": "Laptop stand", "status": "shipped", "carrier": "USPS", "eta_days": 1},
    1008: {"item": "Webcam", "status": "returned", "carrier": None, "eta_days": None},
    1009: {"item": "Trackball mouse", "status": "processing", "carrier": None, "eta_days": 4},
    1010: {"item": "Thunderbolt cable", "status": "delivered", "carrier": "FedEx", "eta_days": 0},
}

TICKETS: list[dict] = []
_ticket_ids = itertools.count(5001)


def require_token(authorization: str | None) -> None:
    if authorization != f"Bearer {API_TOKEN}":
        raise HTTPException(status_code=401, detail="Missing or invalid bearer token")


class TicketRequest(BaseModel):
    order_id: int
    issue: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/orders/{order_id}")
def get_order(order_id: int, authorization: str | None = Header(default=None)) -> dict:
    require_token(authorization)
    order = ORDERS.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=f"No order with id {order_id}")
    return {"order_id": order_id, **order}


@app.post("/tickets")
def create_ticket(req: TicketRequest, authorization: str | None = Header(default=None)) -> dict:
    require_token(authorization)
    if req.order_id not in ORDERS:
        raise HTTPException(status_code=404, detail=f"No order with id {req.order_id}")
    ticket = {"ticket_id": next(_ticket_ids), "order_id": req.order_id, "issue": req.issue, "status": "open"}
    TICKETS.append(ticket)
    return ticket


@app.get("/tickets")
def list_tickets(authorization: str | None = Header(default=None)) -> dict:
    require_token(authorization)
    return {"tickets": TICKETS}
