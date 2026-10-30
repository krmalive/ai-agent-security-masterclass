import csv
import io

from fastapi import APIRouter, Depends, Response

from ..auth import require_admin
from ..errors import ShopFastError
from ..models import ProductUpdate, RefundInput
from ..services import orders, reviews
from ..store import store
from .common import as_http_error

router = APIRouter()


@router.get("/customers")
def list_customers(admin: dict = Depends(require_admin)) -> dict:
    customers = [{key: user.get(key) for key in ("id", "email", "display_name", "active")} for user in store.users.values() if user["role"] == "customer"]
    return {"items": customers, "requested_by": admin["id"]}


@router.get("/orders")
def list_orders(status: str | None = None, admin: dict = Depends(require_admin)) -> dict:
    items = store.snapshot("orders")
    if status:
        items = [order for order in items if order["status"] == status]
    return {"items": items, "requested_by": admin["id"]}


@router.patch("/products/{product_id}")
def update_product(product_id: int, body: ProductUpdate, admin: dict = Depends(require_admin)) -> dict:
    product = store.products.get(product_id)
    if not product:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Product not found")
    product.update(body.model_dump(exclude_none=True))
    product["updated_by"] = admin["id"]
    return product


@router.post("/orders/{order_id}/refund")
async def refund_order(order_id: int, body: RefundInput, admin: dict = Depends(require_admin)) -> dict:
    try:
        result = await orders.refund_order(order_id, body.amount_cents, body.reason)
        result["refunded_by"] = admin["id"]
        return result
    except ShopFastError as error:
        raise as_http_error(error) from error


@router.post("/reviews/{review_id}/hide")
def hide_review(review_id: int, admin: dict = Depends(require_admin)) -> dict:
    try:
        result = reviews.moderate_review(review_id, "hidden")
        result["moderated_by"] = admin["id"]
        return result
    except ShopFastError as error:
        raise as_http_error(error) from error


@router.get("/exports/orders.csv")
def export_orders(admin: dict = Depends(require_admin)) -> Response:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["id", "owner_id", "total_cents", "status", "payment_status", "created_at"])
    writer.writeheader()
    for order in store.orders.values():
        writer.writerow({key: order.get(key) for key in writer.fieldnames})
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=orders.csv"})
