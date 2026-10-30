"""Print a read-only fulfillment preview from the sample data."""
import json
from pathlib import Path

from fulfillment import build_pick_list


DATA = Path(__file__).resolve().parent / "data"


def main() -> None:
    orders = json.loads((DATA / "current_orders.json").read_text())
    stock = json.loads((DATA / "warehouse" / "stock.json").read_text())
    print(json.dumps(build_pick_list(orders, stock), indent=2))


if __name__ == "__main__":
    main()
