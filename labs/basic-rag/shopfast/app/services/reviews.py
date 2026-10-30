from pathlib import Path

from fastapi import UploadFile

from ..config import settings
from ..errors import NotFound
from ..models import ReviewInput
from ..store import store

ALLOWED_MEDIA_TYPES = {"image/jpeg": ".jpg", "image/png": ".png"}


def create_review(user_id: int, body: ReviewInput) -> dict:
    if body.product_id not in store.products:
        raise NotFound("Product not found")
    review_id = store.next_id("reviews", start=8000)
    review = {"id": review_id, "owner_id": user_id, **body.model_dump(), "attachments": [], "status": "published"}
    store.reviews[review_id] = review
    return review


def update_review(user_id: int, review_id: int, body: ReviewInput) -> dict:
    review = store.reviews.get(review_id)
    if not review or review["owner_id"] != user_id:
        raise NotFound("Review not found")
    review.update(body.model_dump())
    return review


async def attach_image(user_id: int, review_id: int, image: UploadFile) -> dict:
    review = store.reviews.get(review_id)
    if not review or review["owner_id"] != user_id:
        raise NotFound("Review not found")
    suffix = ALLOWED_MEDIA_TYPES.get(image.content_type or "")
    if not suffix:
        raise ValueError("JPEG or PNG required")
    safe_name = f"review-{review_id}-{len(review['attachments']) + 1}{suffix}"
    target = Path(settings.media_root) / safe_name
    review["attachments"].append({"filename": safe_name, "storage_path": str(target), "size": image.size})
    return review["attachments"][-1]


def moderate_review(review_id: int, status: str) -> dict:
    review = store.reviews.get(review_id)
    if not review:
        raise NotFound("Review not found")
    review["status"] = status
    return review
