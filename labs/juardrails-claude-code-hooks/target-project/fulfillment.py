"""Build a preview of orders that can be picked from current stock."""


def build_pick_list(orders: list[dict], stock: dict[str, int]) -> dict:
    """Return ready orders, backorders, and remaining stock.

    This starter version has several allocation bugs. See README.md for the rules.
    """
    ready = []
    backordered = []
    remaining_stock = stock.copy()
    for order in orders:
        entry = {
            "order_id": order["id"],
            "sku": order["sku"],
            "quantity": order["quantity"],
        }
        if order["quantity"] <= stock.get(order["sku"], 0):
            ready.append(entry)
        else:
            backordered.append(entry)
    return {
        "ready": ready,
        "backordered": backordered,
        "remaining_stock": remaining_stock,
    }
