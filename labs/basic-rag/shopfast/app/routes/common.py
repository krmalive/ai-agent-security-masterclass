from fastapi import HTTPException

from ..errors import ShopFastError


def as_http_error(error: ShopFastError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=str(error))
