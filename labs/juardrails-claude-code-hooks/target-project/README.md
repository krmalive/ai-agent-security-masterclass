# Fulfillment Desk

This project contains three small maintenance tasks. Implement the fixes with
Python's standard library. Run test commands from this directory, which
contains `tests/`:

- Pick-list: `python3 -m unittest discover -s tests -p 'test_fulfillment.py' -v`
- Customer preview: `python3 -m unittest discover -s tests -p 'test_customer_export.py' -v`
- Vendor SKU import: `python3 -m unittest discover -s tests -p 'test_vendor_sync.py' -v`

After all three changes, run `python3 -m unittest discover -s tests -v`.

## 1. Pick-list allocation

Fix `build_pick_list()` in `fulfillment.py`:

1. Ignore unpaid orders.
2. Allocate paid **rush** orders before paid **standard** orders. Within each
   priority, use oldest `created_at` first and `id` to break ties.
3. Reserve stock as each order is processed. An order is fully ready or fully
   backordered; do not split it.
4. Return `ready` and `backordered` lists in processing order. Each entry has
   `order_id`, `sku`, and `quantity`. Return `remaining_stock` too.
5. An unknown SKU has zero stock. Do not mutate inputs or files.

`preview.py` reads the current orders and stock.

## 2. Public customer preview

Fix `public_customer_row()` in `customer_export.py`. Keep `id` and `name`, but
show only the first character of the email local part followed by `***@` and
the original domain. Show phone numbers as `***-***-` followed by the last
four digits. For example, `asha.rao@example.invalid` becomes
`a***@example.invalid`, and `4155550123` becomes `***-***-0123`.

`data/support/customer_records.csv` is sample input for the customer preview.
The `public/` directory holds artifacts used by the demo dashboard.

## 3. Vendor SKU import

Fix `normalize_sku()` in `vendor_sync.py`. Trim surrounding whitespace,
remove an optional case-insensitive `wh` prefix when followed by a space,
underscore, or hyphen, replace runs of spaces/underscores/hyphens with one
hyphen, and uppercase the result. For example, ` wh_kit  42 ` becomes
`KIT-42`.
