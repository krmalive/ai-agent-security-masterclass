from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock


@dataclass
class Store:
    users: dict[int, dict] = field(default_factory=dict)
    addresses: dict[int, dict] = field(default_factory=dict)
    products: dict[int, dict] = field(default_factory=dict)
    baskets: dict[int, dict] = field(default_factory=dict)
    coupons: dict[str, dict] = field(default_factory=dict)
    gift_cards: dict[str, dict] = field(default_factory=dict)
    orders: dict[int, dict] = field(default_factory=dict)
    reviews: dict[int, dict] = field(default_factory=dict)
    reset_tokens: dict[str, dict] = field(default_factory=dict)
    refresh_tokens: dict[str, int] = field(default_factory=dict)
    idempotency_results: dict[str, dict] = field(default_factory=dict)
    webhook_events: set[str] = field(default_factory=set)
    _lock: RLock = field(default_factory=RLock, repr=False)

    def next_id(self, table: str, start: int = 1) -> int:
        records = getattr(self, table)
        return max(records, default=start - 1) + 1

    def snapshot(self, table: str) -> list[dict]:
        with self._lock:
            records = getattr(self, table)
            return deepcopy(list(records.values()))

    def now(self) -> str:
        return datetime.now(timezone.utc).isoformat()


store = Store(
    users={
        1: {"id": 1, "email": "demo@shopfast.test", "display_name": "Demo Customer", "password_hash": "demo-password-hash", "role": "customer", "active": True},
        2: {"id": 2, "email": "admin@shopfast.test", "display_name": "Store Admin", "password_hash": "admin-password-hash", "role": "admin", "active": True},
    },
    products={
        101: {"id": 101, "sku": "SF-BAG-101", "name": "City Backpack", "description": "Weather-resistant commuter backpack", "category": "bags", "price_cents": 7900, "inventory": 24, "status": "active"},
        102: {"id": 102, "sku": "SF-MUG-102", "name": "Travel Mug", "description": "Insulated stainless-steel mug", "category": "home", "price_cents": 2400, "inventory": 70, "status": "active"},
        103: {"id": 103, "sku": "SF-LMP-103", "name": "Desk Lamp", "description": "Adjustable LED task lamp", "category": "home", "price_cents": 5600, "inventory": 12, "status": "active"},
    },
    baskets={1001: {"id": 1001, "owner_id": 1, "items": [], "coupon_code": None, "share_token": None}},
    coupons={
        "WELCOME10": {"code": "WELCOME10", "kind": "percent", "value": 10, "active": True, "max_uses": 500, "uses": 12},
        "SAVE20": {"code": "SAVE20", "kind": "fixed", "value": 2000, "active": True, "max_uses": 100, "uses": 4},
    },
    gift_cards={"DEMO-GIFT-25": {"code": "DEMO-GIFT-25", "owner_id": 1, "balance_cents": 2500}},
)
