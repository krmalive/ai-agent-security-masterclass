from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Any


class VulnerableTools:
    def __init__(self, export_dir: str = "/app/data/exports") -> None:
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def analyze_invoice(self, content: str) -> Dict[str, Any]:
        return {
            "status": "ok",
            "summary": "Invoice parsed and analyzed.",
            "chars": len(content),
        }

    def process_refund(self, invoice_number: str, amount: float, reason: str) -> Dict[str, Any]:
        return {
            "status": "refunded",
            "invoice_number": invoice_number,
            "amount": amount,
            "reason": reason,
            "refund_id": f"REF-{invoice_number}-{int(time.time())}",
        }

    def export_customer_data(self, query: str) -> Dict[str, Any]:
        payload = {
            "query": query,
            "customers": [
                {"id": "CUST-001", "name": "Alice", "email": "alice@example.com", "card_last4": "4242"},
                {"id": "CUST-002", "name": "Bob", "email": "bob@example.com", "card_last4": "1111"},
            ],
        }
        output = self.export_dir / f"export_{int(time.time())}.json"
        output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {"status": "exported", "path": str(output), "records": len(payload["customers"])}

    def view_financial_records(self, actor_id: str) -> Dict[str, Any]:
        return {
            "status": "ok",
            "actor_id": actor_id,
            "ledger_entries": [
                {"dept": "finance", "type": "wire", "amount": 120000.0},
                {"dept": "ops", "type": "refund", "amount": 9180.0},
            ],
        }
