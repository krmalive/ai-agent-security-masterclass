import copy
import unittest

from fulfillment import build_pick_list


def order(id, sku, quantity, *, paid=True, priority="standard", created_at="2026-09-01T09:00:00Z"):
    return {"id": id, "sku": sku, "quantity": quantity, "paid": paid,
            "priority": priority, "created_at": created_at}


class PickListTests(unittest.TestCase):
    def test_only_paid_orders_are_considered(self):
        orders = [order("unpaid", "KIT", 1, paid=False), order("paid", "KIT", 1)]
        result = build_pick_list(orders, {"KIT": 1})
        self.assertEqual([item["order_id"] for item in result["ready"]], ["paid"])
        self.assertEqual(result["backordered"], [])
        self.assertEqual(result["remaining_stock"], {"KIT": 0})

    def test_rush_order_gets_limited_stock_first(self):
        orders = [order("standard", "KIT", 1), order("rush", "KIT", 1, priority="rush")]
        result = build_pick_list(orders, {"KIT": 1})
        self.assertEqual([item["order_id"] for item in result["ready"]], ["rush"])
        self.assertEqual([item["order_id"] for item in result["backordered"]], ["standard"])

    def test_older_order_wins_within_same_priority(self):
        orders = [order("new", "KIT", 1, created_at="2026-09-02T09:00:00Z"),
                  order("old", "KIT", 1, created_at="2026-09-01T09:00:00Z")]
        result = build_pick_list(orders, {"KIT": 1})
        self.assertEqual([item["order_id"] for item in result["ready"]], ["old"])
        self.assertEqual([item["order_id"] for item in result["backordered"]], ["new"])

    def test_order_id_breaks_same_priority_and_timestamp_ties(self):
        orders = [order("B", "KIT", 1), order("A", "KIT", 1)]
        result = build_pick_list(orders, {"KIT": 1})
        self.assertEqual([item["order_id"] for item in result["ready"]], ["A"])
        self.assertEqual([item["order_id"] for item in result["backordered"]], ["B"])

    def test_stock_is_reserved_and_orders_are_not_split(self):
        orders = [order("first", "KIT", 2), order("second", "KIT", 2)]
        result = build_pick_list(orders, {"KIT": 3})
        self.assertEqual([item["order_id"] for item in result["ready"]], ["first"])
        self.assertEqual([item["order_id"] for item in result["backordered"]], ["second"])
        self.assertEqual(result["remaining_stock"], {"KIT": 1})

    def test_missing_sku_is_backordered(self):
        result = build_pick_list([order("one", "MISSING", 2)], {"KIT": 3})
        self.assertEqual(result["ready"], [])
        self.assertEqual(result["backordered"],
                         [{"order_id": "one", "sku": "MISSING", "quantity": 2}])
        self.assertEqual(result["remaining_stock"], {"KIT": 3})

    def test_inputs_are_not_mutated(self):
        orders = [order("one", "KIT", 2)]
        stock = {"KIT": 3}
        original_orders, original_stock = copy.deepcopy(orders), stock.copy()
        build_pick_list(orders, stock)
        self.assertEqual(orders, original_orders)
        self.assertEqual(stock, original_stock)


if __name__ == "__main__":
    unittest.main()
