from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ..auth import current_user
from ..errors import ShopFastError
from ..models import ReviewInput
from ..services import reviews
from .common import as_http_error

router = APIRouter()


@router.post("", status_code=201)
def create_review(body: ReviewInput, user: dict = Depends(current_user)) -> dict:
    try:
        return reviews.create_review(user["id"], body)
    except ShopFastError as error:
        raise as_http_error(error) from error


@router.put("/{review_id}")
def update_review(review_id: int, body: ReviewInput, user: dict = Depends(current_user)) -> dict:
    try:
        return reviews.update_review(user["id"], review_id, body)
    except ShopFastError as error:
        raise as_http_error(error) from error


@router.post("/{review_id}/attachments", status_code=201)
async def attach_image(
    review_id: int,
    image: UploadFile = File(...),
    user: dict = Depends(current_user),
) -> dict:
    try:
        return await reviews.attach_image(user["id"], review_id, image)
    except ShopFastError as error:
        raise as_http_error(error) from error
    except ValueError as error:
        raise HTTPException(status_code=415, detail=str(error)) from error
